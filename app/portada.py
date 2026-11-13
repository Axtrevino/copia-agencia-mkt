"""SEO: la imagen principal y la miniatura de un artículo de blog (sin texto).

GPT Image hace una foto editorial 3:2 sin referencias (para que no copie logos ni textos de las
piezas sociales); aquí se recorta al centro a 16:9 y sale la miniatura. Quién aparece y dónde sale
de `marca.json` → `blog.personas_en` y `blog.lugar_en`. La llamada a GPT Image llega inyectada:
las pruebas no salen a la red.
"""

from __future__ import annotations

import base64
import hashlib
import io
from collections.abc import Callable

from PIL import Image

from app import marcas
from app.imagen import Imagen
from app.research import ErrorHTTP

ANCHO, ALTO = 1600, 900
MINI_ANCHO, MINI_ALTO = 800, 450
TAMANO = "1536x1024"
MAX_BYTES = 1_000_000  # la portada pesa menos de 1 MB (CMS y n8n)
CALIDADES = (85, 80, 75, 70, 60, 50)

PERSONAS_POR_OMISION = "people from the brand's target audience in everyday situations"
LUGAR_POR_OMISION = "a real everyday environment in Mexico, consistent with the topic"

PROMPT = """Realistic editorial photograph for the header of a blog article.
Setting: {lugar}.
People: {personas}.
Scene: {escena}.
Style: natural light, candid moment, shallow depth of field, warm and professional tone,
wide horizontal composition with the main subject near the center.
Strictly no text, no letters, no numbers, no words, no logos, no brand names, no watermarks.
Any screens, papers or signs in the scene must be blank or out of focus.{extra}"""


def _sin_comillas(texto: str) -> str:
    """Quita comillas para que GPT Image no lo tome como un texto a dibujar."""
    for c in "\"'«»“”‘’`":
        texto = texto.replace(c, "")
    return " ".join(texto.split())


def armar_prompt(marca: str, titulo: str, escena: str = "") -> str:
    blog = marcas.config(marca).get("blog") or {}
    escena = _sin_comillas(escena) or (
        f"a moment that illustrates an article about {_sin_comillas(titulo)}"
    )
    extra = f"\n{blog['evitar_en']}" if blog.get("evitar_en") else ""
    return PROMPT.format(
        lugar=blog.get("lugar_en") or LUGAR_POR_OMISION,
        personas=blog.get("personas_en") or PERSONAS_POR_OMISION,
        escena=escena,
        extra=extra,
    )


def a_portada(imagen: Image.Image) -> Image.Image:
    """Recorta al centro a 16:9 (sin deformar) y escala a 1600 × 900 RGB."""
    imagen = imagen.convert("RGB")
    w, h = imagen.size
    objetivo = ANCHO / ALTO
    if w / h > objetivo:
        nuevo = round(h * objetivo)
        x0 = (w - nuevo) // 2
        imagen = imagen.crop((x0, 0, x0 + nuevo, h))
    elif w / h < objetivo:
        nuevo = round(w / objetivo)
        y0 = (h - nuevo) // 2
        imagen = imagen.crop((0, y0, w, y0 + nuevo))
    return imagen.resize((ANCHO, ALTO), Image.LANCZOS)


def a_jpeg(imagen: Image.Image) -> bytes:
    """JPEG RGB en calidad ~85; baja la calidad hasta que pese menos de 1 MB."""
    for calidad in CALIDADES:
        buf = io.BytesIO()
        imagen.convert("RGB").save(buf, "JPEG", quality=calidad, optimize=True)
        if buf.tell() < MAX_BYTES:
            return buf.getvalue()
    raise ValueError("la portada no baja de 1 MB")


def leer_pedido(pedido: dict) -> tuple[str, str, str, str, int]:
    if not isinstance(pedido, dict):
        raise ErrorHTTP(422, "el cuerpo debe ser un objeto JSON")
    marca = str(pedido.get("marca") or "")
    try:
        marcas.config(marca)
    except marcas.MarcaDesconocida as exc:
        raise ErrorHTTP(422, str(exc)) from None
    slug = str(pedido.get("slug") or "").strip()
    if not slug:
        raise ErrorHTTP(422, "falta slug")
    titulo = str(pedido.get("titulo") or "").strip()
    if not titulo:
        raise ErrorHTTP(422, "falta titulo")
    try:
        version = int(pedido.get("version") or 1)
    except (TypeError, ValueError):
        raise ErrorHTTP(422, "version debe ser un número") from None
    escena = str(pedido.get("escena") or "").strip()
    return marca, slug, titulo, escena, version


def atender(
    pedido: dict,
    token: str | None,
    token_esperado: str | None,
    generar: Callable[[str], Imagen],
) -> dict:
    """Lógica de POST /portada: token y pedido se revisan antes de pagar la imagen."""
    from app.servicio import token_valido

    if not token_valido(token, token_esperado):
        raise ErrorHTTP(401, "token inválido")
    marca, slug, titulo, escena, version = leer_pedido(pedido)
    prompt = armar_prompt(marca, titulo, escena)
    try:
        imagen = generar(prompt)
    except RuntimeError as exc:  # error de OpenAI o falta la llave: el mensaje no trae la llave
        raise ErrorHTTP(502, str(exc)) from None
    portada = a_portada(Image.open(io.BytesIO(imagen.png)))
    jpeg = a_jpeg(portada)
    mini = a_jpeg(portada.resize((MINI_ANCHO, MINI_ALTO), Image.LANCZOS))
    return {
        "archivo": f"{slug}-v{version}.jpg",
        "portada_jpeg_b64": base64.b64encode(jpeg).decode(),
        "miniatura_jpeg_b64": base64.b64encode(mini).decode(),
        "ancho": portada.width,
        "alto": portada.height,
        "bytes": len(jpeg),
        "md5": hashlib.md5(jpeg).hexdigest(),
        "modelo": imagen.modelo,
        "costo_usd": imagen.costo_usd,
        "uso": imagen.uso,
        "prompt": prompt,
    }
