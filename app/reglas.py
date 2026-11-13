"""Revisión de reglas de la marca antes de gastar en una imagen o publicar un texto.

Todo sale de `marca.json` y de la ficha; el código no conoce ninguna industria:
- `palabras_prohibidas`: palabras o frases que nunca deben aparecer (p. ej. promesas que la marca
  no puede hacer). Bloquean.
- `frases_trilladas`: frases que suenan genéricas. Solo avisan.
- `disclaimer_obligatorio`: si es `true`, el texto debe llevar el `disclaimer` de «Datos
  verificados» tal cual.

Si la industria de la marca tiene reglas legales (salud, finanzas, alcohol…), se escriben como
`palabras_prohibidas` y en la ficha; si hace falta lógica (p. ej. cifras que siempre van con su
leyenda), se agrega aquí una función nueva. Lógica pura: sin red.
"""

from __future__ import annotations

import re
import unicodedata

from app import marcas
from app.datos import datos_verificados


def _normal(texto: str) -> str:
    sin_acentos = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in sin_acentos if not unicodedata.combining(c)).lower()


def _aparece(frase: str, texto: str) -> bool:
    frase = _normal(frase).strip()
    if not frase:
        return False
    return re.search(rf"(?<!\w){re.escape(frase)}(?!\w)", _normal(texto)) is not None


def revisar(marca: str, texto: str, tipo: str = "post", datos: dict | None = None) -> dict:
    """`{"ok": bool, "bloqueos": [...], "avisos": [...]}`; cada uno con `regla` y `detalle`.

    `tipo` ("post" o "articulo") queda para reglas que solo apliquen a uno de los dos.
    """
    cfg = marcas.config(marca)
    bloqueos, avisos = [], []
    for frase in cfg["palabras_prohibidas"]:
        if _aparece(frase, texto):
            bloqueos.append({"regla": "palabra prohibida", "detalle": f"«{frase}»"})
    for frase in cfg["frases_trilladas"]:
        if _aparece(frase, texto):
            avisos.append({"regla": "frase trillada", "detalle": f"«{frase}»"})
    if cfg["disclaimer_obligatorio"]:
        if datos is None:
            datos = datos_verificados(marcas.ficha(marca))
        disclaimer = str(datos.get("disclaimer") or "").strip()
        if not disclaimer:
            bloqueos.append(
                {"regla": "disclaimer", "detalle": "la ficha no trae «disclaimer» en Datos"}
            )
        elif disclaimer not in (texto or ""):
            bloqueos.append({"regla": "disclaimer", "detalle": "falta el disclaimer exacto"})
    if not cfg["copy"]["emojis"] and tipo == "post":
        if re.search(r"[\U0001F300-\U0001FAFF☀-➿]", texto or ""):
            bloqueos.append({"regla": "emojis", "detalle": "esta marca no usa emojis"})
    return {"ok": not bloqueos, "bloqueos": bloqueos, "avisos": avisos}
