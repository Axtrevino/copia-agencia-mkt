"""Textos de los prompts de GPT Image que no son la pieza base.

- `con_ajustes_imagen`: agrega al prompt de `POST /` la sección «## Imagen» de `ajustes.md` de la
  marca, como guía visual que nunca manda sobre el logo, los textos exactos ni el legal.
- `armar_prompt_edicion`: el prompt de `POST /editar`, que cambia solo los textos de una pieza ya
  hecha (la imagen actual entra a `/images/edits`) y deja igual la foto, el diseño y el logo.

Lógica pura: sin red y sin `os.environ`.
"""

from __future__ import annotations

from app import marcas
from app.pieza import PedidoMalo, Textos, acento_de, sistemas_de, validar

MAX_AJUSTES_IMAGEN = 1500
_AJUSTES_IMAGEN = (
    "Extra visual guidance from the brand owner (may be written in Spanish). It never overrides "
    "the logo rules, the exact texts or the legal text, and none of it is text to render:"
)


def con_ajustes_imagen(prompt: str, ajustes_imagen: str = "") -> str:
    """El prompt de la pieza con la sección «Imagen» de los ajustes al final (si hay)."""
    ajustes_imagen = (ajustes_imagen or "").strip()[:MAX_AJUSTES_IMAGEN]
    if not ajustes_imagen:
        return prompt
    return f"{prompt}\n\n{_AJUSTES_IMAGEN}\n{ajustes_imagen}"


CAMPOS_EDITABLES = (
    ("titular", "Headline"),
    ("kicker", "Kicker (small uppercase label)"),
    ("subtitulo", "Subtitle"),
    ("cta", "Button"),
    ("url", "URL"),
    ("disclaimer", "Legal text"),
)

BASE_EDICION = """Edit the attached image. It is a finished social media post for {marca}.
Change ONLY the text elements listed below and keep everything else identical: the photo, the
people (faces, hands, clothes, poses), the background, the layout, the logo, the colors, the
graphic accents and every other text. Do not regenerate, reframe, crop, move or redraw
anything else.

Text changes (render each new text EXACTLY as written: same spelling, accents, capitalization and
punctuation; do not add, translate or change any other word):
{cambios}

Each new text uses the same font, weight, size, color, alignment and position as the text it
replaces. If a new text is longer, wrap it inside the same area, never over faces, hands or the
logo. Where a text is removed, fill its area with the background that surrounds it.

Context of the current image (do not change it): layout: {sistema} Photo: {escena}

Output the same vertical 4:5 post with the logo and every text fully visible."""


def armar_prompt_edicion(
    sistema: str, antes: Textos, despues: Textos, escena: str, marca: str
) -> tuple[str, list[str]]:
    """Prompt para editar los textos de una pieza existente y la lista de campos que cambian.

    Valida los textos nuevos con las mismas reglas que la pieza. Sin cambios, `PedidoMalo`.
    """
    validar(sistema, despues, marca)
    distintos = [c for c in Textos.__dataclass_fields__ if getattr(antes, c) != getattr(despues, c)]
    if not distintos:
        raise PedidoMalo("no hay textos distintos entre textos_antes y textos")
    renglones = []
    for campo, nombre in CAMPOS_EDITABLES:
        viejo, nuevo = getattr(antes, campo).strip(), getattr(despues, campo).strip()
        if viejo == nuevo:
            continue
        if viejo and nuevo:
            renglones.append(f'- {nombre}: replace "{viejo}" with "{nuevo}"')
        elif nuevo:
            renglones.append(f'- {nombre}: add "{nuevo}" where the layout has room for it')
        else:
            renglones.append(f'- {nombre}: remove "{viejo}"')
    if despues.palabra_acento and ("palabra_acento" in distintos or "titular" in distintos):
        renglones.append(
            f'- In the headline, render the last word "{despues.palabra_acento}" '
            f"{acento_de(marca)}, like the accent word in the current image"
        )
    elif antes.palabra_acento and not despues.palabra_acento:
        renglones.append("- The headline has no accent word: render all of it in one color")
    if not renglones:
        raise PedidoMalo("no hay textos distintos entre textos_antes y textos")
    prompt = BASE_EDICION.format(
        marca=marcas.config(marca).get("nombre") or marca,
        cambios="\n".join(renglones),
        sistema=sistemas_de(marca)[sistema],
        escena=escena.strip() or "as it is in the attached image.",
    )
    return prompt, distintos
