"""La pieza completa la hace GPT Image: foto, diseño, textos y logo.

Aquí solo se arma el prompt con las reglas de la marca (`marcas/<slug>/marca.json`) y se deja la
imagen en el formato de publicación (4:5, JPEG RGB 1080 × 1350 < 10 MB). Cada marca tiene sus
propias plantillas («sistemas» de composición) y sus propias reglas visuales: nunca se mezclan.
Lógica pura: sin red y sin `os.environ`.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image

from app import marcas

ANCHO, ALTO = 1080, 1350
MAX_BYTES = 10 * 1024 * 1024

BASE = """Create one finished Instagram/Facebook feed post for {nombre}, {descripcion}. From the
attached files keep only colors, type and logo: the layout, scene and headline come from this
prompt, never from an attached image.

Brand rules:
{reglas_visuales}
- Logo: reproduce the attached official {nombre} logo EXACTLY in the position the layout says.
  {logo_desc}Do not redraw, restyle, recolor, distort or invent any other logo.
- Photo: {foto}
- Never put text over faces, hands or the main action. No other words, signs, brands or
  watermarks anywhere in the image.

Layout system: {sistema}

Scene: {escena}

Text to render EXACTLY as written (same spelling, accents and punctuation; do not add,
translate or change any word):
{textos}

Format: vertical 4:5 feed post using the whole canvas, mobile-first, understood in one or two
seconds. Keep the logo, every text and the button fully visible and at least 72 px away from
every edge; nothing may touch or be cut by the border. Any legal text must be complete and
readable on a phone."""

FOTO_POR_OMISION = (
    "editorial, natural, relatable people in everyday places, candid, nobody looking at the "
    "camera, natural light that fits the place, clothing with clearly different colors. Never "
    "stock-bank looking."
)


class PedidoMalo(ValueError):
    """El pedido no cumple las reglas de la marca (faltan datos o el texto es demasiado largo)."""


@dataclass
class Textos:
    titular: str
    kicker: str = ""
    palabra_acento: str = ""
    subtitulo: str = ""
    cta: str = ""
    url: str = ""
    disclaimer: str = ""


def _config(marca: str) -> dict:
    try:
        return marcas.config(marca)
    except marcas.MarcaDesconocida as exc:
        raise PedidoMalo(str(exc)) from None


def sistemas_de(marca: str) -> dict[str, str]:
    """Todas las plantillas que acepta la marca: nombre → descripción."""
    return {k: v["descripcion"] for k, v in _config(marca)["plantillas"].items()}


def sistemas_para_proponer(marca: str) -> tuple[str, ...]:
    """Las plantillas que se ofrecen para posts nuevos (las que no traen `"proponer": false`)."""
    plantillas = _config(marca)["plantillas"]
    return tuple(k for k, v in plantillas.items() if v.get("proponer", True))


def plantilla(marca: str, sistema: str) -> dict:
    plantillas = _config(marca)["plantillas"]
    if sistema not in plantillas:
        raise PedidoMalo(f"sistema desconocido: {sistema!r}; usa uno de {', '.join(plantillas)}")
    return plantillas[sistema]


def archivos_de(marca: str, sistema: str) -> list[str]:
    """Rutas relativas (dentro de la carpeta de la marca) que se adjuntan a GPT Image.

    El logo que pide la plantilla (o todos los de `logos/` si no dice) y, si trae, una referencia.
    """
    p = plantilla(marca, sistema)
    if p.get("logo"):
        rutas = [f"logos/{p['logo']}"]
    else:
        rutas = [f"logos/{r.name}" for r in marcas.archivos(marca, "logos")]
    if p.get("referencia"):
        rutas.append(f"referencias/{p['referencia']}")
    return rutas


def limites_de(marca: str) -> dict[str, int]:
    return _config(marca)["limites"]


def validar(sistema: str, t: Textos, marca: str) -> None:
    sistemas = sistemas_de(marca)
    if sistema not in sistemas:
        raise PedidoMalo(f"sistema desconocido: {sistema!r}; usa uno de {', '.join(sistemas)}")
    if not t.titular.strip():
        raise PedidoMalo("falta el titular")
    for campo, limite in limites_de(marca).items():
        valor = getattr(t, campo, "")
        if len(valor) > limite:
            raise PedidoMalo(f"{campo} tiene {len(valor)} caracteres; el máximo es {limite}")
    if t.palabra_acento and not t.titular.rstrip().endswith(t.palabra_acento):
        raise PedidoMalo("palabra_acento debe ser la última palabra del titular")


def acento_de(marca: str) -> str:
    return _config(marca).get("acento_en") or "in the brand's accent color"


def armar_prompt(sistema: str, t: Textos, escena: str, marca: str) -> str:
    """Prompt completo para GPT Image con las reglas de la marca y los textos exactos."""
    validar(sistema, t, marca)
    cfg = _config(marca)
    renglones = [f'- Headline: "{t.titular}"']
    if t.palabra_acento:
        renglones.append(f'  (render the last word "{t.palabra_acento}" {acento_de(marca)})')
    etiquetas = [
        ("kicker", "Kicker (small uppercase label)"),
        ("subtitulo", "Subtitle"),
        ("cta", "Button"),
        ("url", "URL"),
        ("disclaimer", "Legal text (small, fully legible, exact)"),
    ]
    for campo, nombre in etiquetas:
        valor = getattr(t, campo)
        if valor:
            renglones.append(f'- {nombre}: "{valor}"')
    p = plantilla(marca, sistema)
    logo_desc = f"{p['logo_desc']} " if p.get("logo_desc") else ""
    reglas = cfg.get("reglas_visuales_en") or []
    if isinstance(reglas, str):
        reglas = [reglas]
    return BASE.format(
        nombre=cfg.get("nombre") or marca,
        descripcion=cfg.get("descripcion_en") or "a brand",
        reglas_visuales="\n".join(f"- {r}" for r in reglas),
        logo_desc=logo_desc,
        foto=cfg.get("foto_en") or FOTO_POR_OMISION,
        sistema=p["descripcion"],
        escena=escena.strip(),
        textos="\n".join(renglones),
    )


def a_formato(imagen: Image.Image) -> Image.Image:
    """Recorta al centro a 4:5 (sin deformar) y escala a 1080 × 1350 RGB."""
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


def a_jpeg(pieza: Image.Image) -> bytes:
    """JPEG RGB < 10 MB (baja la calidad si hiciera falta)."""
    for calidad in (92, 85, 75):
        buf = io.BytesIO()
        pieza.convert("RGB").save(buf, "JPEG", quality=calidad, optimize=True)
        if buf.tell() < MAX_BYTES:
            return buf.getvalue()
    raise ValueError("la pieza no baja de 10 MB")
