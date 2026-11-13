"""El servicio «pieza» sin Modal: valida el pedido, pide la pieza a GPT Image y la deja lista
para publicar. Lo externo (la llamada a OpenAI, las referencias) llega inyectado.

`atender_edicion` (`POST /editar`) cambia solo los textos de la pieza actual en lugar de
rehacerla: la imagen actual entra a `/images/edits` y la respuesta tiene la forma de `POST /`.
"""

from __future__ import annotations

import base64
import binascii
import hmac
import io
from collections.abc import Callable
from dataclasses import fields

from PIL import Image, UnidentifiedImageError

from app import marcas
from app.edicion import armar_prompt_edicion, con_ajustes_imagen
from app.imagen import Imagen, Referencia
from app.pieza import PedidoMalo, Textos, a_formato, a_jpeg, armar_prompt, sistemas_de
from app.reglas import revisar

CAMPOS_TEXTO = {f.name for f in fields(Textos)}
MAX_IMAGEN_EDICION = 15 * 1024 * 1024  # la pieza actual pesa < 10 MB (JPEG 1080 × 1350)


def token_valido(recibido: str | None, esperado: str | None) -> bool:
    """Compara en tiempo constante; sin token configurado no se atiende a nadie."""
    if not esperado or not recibido:
        return False
    return hmac.compare_digest(recibido.encode(), esperado.encode())


def _marca_y_sistema(pedido: dict) -> tuple[str, str]:
    marca = pedido.get("marca")
    try:
        marcas.config(str(marca or ""))
    except marcas.MarcaDesconocida:
        raise PedidoMalo(f"marca desconocida: {marca!r}") from None
    sistema = pedido.get("sistema")
    sistemas = sistemas_de(marca)
    if sistema not in sistemas:
        raise PedidoMalo(f"sistema desconocido: {sistema!r}; usa uno de {', '.join(sistemas)}")
    return marca, sistema


def _post_y_version(pedido: dict) -> tuple[str, int]:
    post_id = str(pedido.get("post_id") or "").strip()
    if not post_id:
        raise PedidoMalo("falta post_id")
    try:
        version = int(pedido.get("version") or 1)
    except (TypeError, ValueError):
        raise PedidoMalo("version debe ser un número") from None
    return post_id, version


def leer_pedido(pedido: dict) -> tuple[str, str, str, int, str, Textos]:
    if not isinstance(pedido, dict):
        raise PedidoMalo("el cuerpo debe ser un objeto JSON")
    marca, sistema = _marca_y_sistema(pedido)
    post_id, version = _post_y_version(pedido)
    escena = str(pedido.get("escena") or "").strip()
    if not escena:
        raise PedidoMalo("falta escena (qué se ve en la foto)")
    crudos = {k: str(v) for k, v in (pedido.get("textos") or {}).items() if k in CAMPOS_TEXTO}
    crudos.setdefault("titular", "")
    return marca, post_id, sistema, version, escena, Textos(**crudos)


def atender(
    pedido: dict,
    generar: Callable[[str, list[Referencia]], Imagen],
    referencias: list[Referencia],
    ajustes_imagen: str = "",
) -> dict:
    """Pedido → pieza final. Valida todo antes de pagar la imagen.

    `ajustes_imagen`: la sección «## Imagen» de `ajustes.md` de la marca.
    """
    marca, post_id, sistema, version, escena, textos = leer_pedido(pedido)
    prompt = armar_prompt(sistema, textos, escena, marca)  # valida largos y acento
    prompt = con_ajustes_imagen(prompt, ajustes_imagen)
    imagen = generar(prompt, referencias)
    return _resultado(post_id, version, sistema, imagen, prompt)


def _textos(crudos, nombre: str) -> Textos:
    if not isinstance(crudos, dict):
        raise PedidoMalo(f"{nombre} debe ser un objeto con los textos de la imagen")
    datos = {k: str(v) for k, v in crudos.items() if k in CAMPOS_TEXTO and v is not None}
    datos.setdefault("titular", "")
    return Textos(**datos)


def _imagen_actual(b64, post_id: str) -> Referencia:
    """La pieza actual (base64) como archivo para `/images/edits`; valida que sea una imagen."""
    if not isinstance(b64, str) or not b64.strip():
        raise PedidoMalo("falta imagen_b64 (la pieza actual en base64)")
    texto = b64.strip()
    if texto.startswith("data:") and "," in texto:
        texto = texto.split(",", 1)[1]  # acepta también una data URL
    try:
        datos = base64.b64decode(texto, validate=True)
    except (binascii.Error, ValueError):
        raise PedidoMalo("imagen_b64 no es base64 válido") from None
    if len(datos) > MAX_IMAGEN_EDICION:
        raise PedidoMalo("la imagen actual pesa más de 15 MB")
    try:
        formato = Image.open(io.BytesIO(datos)).format or ""
    except (UnidentifiedImageError, OSError):
        raise PedidoMalo("imagen_b64 no es una imagen") from None
    extension = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}.get(formato)
    if not extension:
        raise PedidoMalo(f"la imagen actual debe ser JPEG, PNG o WEBP (llegó {formato or '?'})")
    return Referencia(f"{post_id}-actual.{extension}", datos)


def leer_edicion(pedido: dict, datos: dict | None = None):
    """Valida el pedido de `/editar` sin gastar: marca, sistema, textos y la imagen actual.

    `datos` («Datos verificados» de la ficha) fija el disclaimer si la marca lo exige.
    """
    if not isinstance(pedido, dict):
        raise PedidoMalo("el cuerpo debe ser un objeto JSON")
    marca, sistema = _marca_y_sistema(pedido)
    post_id, version = _post_y_version(pedido)
    escena = str(pedido.get("escena") or "").strip()
    antes = _textos(pedido.get("textos_antes"), "textos_antes")
    despues = _textos(pedido.get("textos"), "textos")
    cfg = marcas.config(marca)
    disclaimer = str((datos or {}).get("disclaimer") or "").strip()
    if cfg["disclaimer_obligatorio"] and disclaimer and despues.disclaimer.strip() != disclaimer:
        raise PedidoMalo("el disclaimer de la pieza debe ser el de «Datos verificados» de la ficha")
    # valida largos y acento, y que haya algo distinto
    prompt, editados = armar_prompt_edicion(sistema, antes, despues, escena, marca)
    visibles = [despues.kicker, despues.titular, despues.subtitulo, despues.cta, despues.disclaimer]
    revision = revisar(marca, "\n".join(t for t in visibles if t), "imagen", datos=datos)
    if not revision["ok"]:
        raise PedidoMalo("; ".join(f"{b['regla']}: {b['detalle']}" for b in revision["bloqueos"]))
    actual = _imagen_actual(pedido.get("imagen_b64"), post_id)
    return post_id, sistema, version, prompt, editados, actual


def atender_edicion(
    pedido: dict,
    editar: Callable[[str, Referencia], Imagen],
    datos: dict | None = None,
) -> dict:
    """Pedido de `/editar` → pieza con los textos nuevos. Valida todo antes de pagar la edición."""
    post_id, sistema, version, prompt, editados, actual = leer_edicion(pedido, datos)
    imagen = editar(prompt, actual)
    return {
        **_resultado(post_id, version, sistema, imagen, prompt),
        "editados": editados,
        "alcance": "textos",
    }


def _resultado(post_id: str, version: int, sistema: str, imagen: Imagen, prompt: str) -> dict:
    """La imagen de OpenAI en el formato de publicación (JPEG 1080 × 1350) y sus datos."""
    pieza = a_formato(Image.open(io.BytesIO(imagen.png)))
    jpeg = a_jpeg(pieza)
    return {
        "post_id": post_id,
        "version": version,
        "sistema": sistema,
        "archivo": f"{post_id}-v{version}.jpg",
        "pieza_jpeg_b64": base64.b64encode(jpeg).decode(),
        "ancho": pieza.width,
        "alto": pieza.height,
        "bytes": len(jpeg),
        "modelo": imagen.modelo,
        "costo_usd": imagen.costo_usd,
        "uso": imagen.uso,
        "prompt": prompt,
    }
