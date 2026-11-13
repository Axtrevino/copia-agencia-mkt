"""La pieza con la API de imágenes de OpenAI. Solo librería estándar.

Con imágenes de referencia (logos oficiales y piezas aprobadas) usa `/images/edits`; sin ellas,
`/images/generations`. `editar` cambia los textos de una pieza ya hecha (la imagen actual es la
única entrada de `/images/edits`). La función `enviar` es inyectable: las pruebas no salen a la red.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable
from dataclasses import dataclass

BASE_URL = "https://api.openai.com/v1/images"


@dataclass
class Imagen:
    png: bytes
    modelo: str
    costo_usd: float | None
    uso: dict


@dataclass
class Referencia:
    nombre: str
    datos: bytes


def multipart(campos: dict[str, str], archivos: list[Referencia]) -> tuple[bytes, str]:
    """Cuerpo multipart/form-data con los campos y las imágenes (`image[]`)."""
    limite = uuid.uuid4().hex
    partes: list[bytes] = []
    for k, v in campos.items():
        partes.append(
            f'--{limite}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
        )
    for ref in archivos:
        tipo = mimetypes.guess_type(ref.nombre)[0] or "image/png"
        cabecera = (
            f'--{limite}\r\nContent-Disposition: form-data; name="image[]"; '
            f'filename="{ref.nombre}"\r\nContent-Type: {tipo}\r\n\r\n'
        )
        partes.append(cabecera.encode() + ref.datos + b"\r\n")
    partes.append(f"--{limite}--\r\n".encode())
    return b"".join(partes), f"multipart/form-data; boundary={limite}"


def _enviar_urllib(url: str, cuerpo: bytes, tipo: str, llave: str, timeout: int = 300) -> dict:
    req = urllib.request.Request(
        url, data=cuerpo, headers={"Authorization": f"Bearer {llave}", "Content-Type": tipo}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:  # el mensaje de OpenAI no trae la llave
        detalle = exc.read()[:400].decode(errors="replace")
        raise RuntimeError(f"OpenAI respondió {exc.code}: {detalle}") from None


def costo(uso: dict, usd_m_entrada: float, usd_m_salida: float) -> float | None:
    """Costo estimado con los tokens que reporta OpenAI y el precio por millón configurado."""
    if not uso:
        return None
    entrada = uso.get("input_tokens") or 0
    salida = uso.get("output_tokens") or 0
    return round(entrada * usd_m_entrada / 1e6 + salida * usd_m_salida / 1e6, 4)


def generar(
    prompt: str,
    llave: str,
    referencias: list[Referencia] | None = None,
    modelo: str = "gpt-image-2",
    tamano: str = "1088x1360",
    calidad: str = "high",
    usd_m_entrada: float = 5.0,
    usd_m_salida: float = 32.0,
    enviar: Callable[[str, bytes, str, str], dict] = _enviar_urllib,
    fidelidad: str = "",
) -> Imagen:
    """Pide una imagen; `fidelidad` (p. ej. "high") va como `input_fidelity` solo en edits."""
    if not llave:
        raise RuntimeError("falta OPENAI_API_KEY en el secret de Modal")
    if not prompt.strip():
        raise ValueError("prompt vacío")
    campos = {"model": modelo, "prompt": prompt, "size": tamano, "quality": calidad, "n": "1"}
    if referencias:
        if fidelidad:
            campos["input_fidelity"] = fidelidad
        cuerpo, tipo = multipart(campos, referencias)
        url = f"{BASE_URL}/edits"
    else:
        cuerpo, tipo = json.dumps({**campos, "n": 1}).encode(), "application/json"
        url = f"{BASE_URL}/generations"
    datos = enviar(url, cuerpo, tipo, llave)
    try:
        b64 = datos["data"][0]["b64_json"]
    except (KeyError, IndexError, TypeError):
        raise RuntimeError(f"OpenAI no devolvió imagen: {str(datos)[:300]}") from None
    uso = datos.get("usage") or {}
    return Imagen(
        png=base64.b64decode(b64),
        modelo=modelo,
        costo_usd=costo(uso, usd_m_entrada, usd_m_salida),
        uso=uso,
    )


def editar(
    prompt: str,
    llave: str,
    actual: Referencia,
    modelo: str = "gpt-image-2",
    tamano: str = "1088x1360",
    calidad: str = "high",
    fidelidad: str = "high",
    usd_m_entrada: float = 5.0,
    usd_m_salida: float = 32.0,
    enviar: Callable[[str, bytes, str, str], dict] = _enviar_urllib,
) -> Imagen:
    """Edita la pieza actual con `/images/edits` (mismo modelo, tamaño y calidad que la pieza).

    Pide `input_fidelity` alto para conservar foto, caras y logo. Si el modelo no acepta ese
    parámetro (OpenAI responde un error que lo nombra), reintenta una vez sin él.
    """

    def pedir(f: str) -> Imagen:
        return generar(
            prompt,
            llave,
            [actual],
            modelo=modelo,
            tamano=tamano,
            calidad=calidad,
            usd_m_entrada=usd_m_entrada,
            usd_m_salida=usd_m_salida,
            enviar=enviar,
            fidelidad=f,
        )

    try:
        return pedir(fidelidad)
    except RuntimeError as exc:
        if not fidelidad or "input_fidelity" not in str(exc):
            raise
        return pedir("")
