"""Configuración de las marcas: todo lo que cambia de una marca a otra vive en `marcas/<slug>/`.

    marcas/<slug>/
      marca.json        reglas que aplica el código (plantillas, límites, liga, colores, palabras)
      ficha.md          voz, público, producto, datos verificados, hashtags (la lee GPT)
      ajustes.md        ajustes de tono del dueño de la marca; mandan sobre la ficha (opcional)
      logos/            logos oficiales (PNG)
      referencias/      piezas aprobadas que sirven de referencia visual (JPG)

Nada de la marca se escribe en el código. Para agregar una marca se copia `marcas/marca-a/`.
Lógica pura: sin red y sin `os.environ`.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

# En el repo (pruebas y local) o en la imagen de Modal (`/marcas`).
DIRECTORIOS = (Path(__file__).resolve().parent.parent / "marcas", Path("/marcas"))
_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")


class MarcaDesconocida(ValueError):
    """No existe `marcas/<slug>/marca.json`."""


def directorio(slug: str, directorios: tuple[Path, ...] = DIRECTORIOS) -> Path:
    if not isinstance(slug, str) or not _SLUG.match(slug):
        raise MarcaDesconocida(f"marca inválida: {slug!r}")
    for base in directorios:
        ruta = Path(base) / slug
        if (ruta / "marca.json").exists():
            return ruta
    raise MarcaDesconocida(f"marca sin configuración: {slug!r} (falta marcas/{slug}/marca.json)")


@lru_cache(maxsize=16)
def config(slug: str) -> dict:
    """`marca.json` de la marca, con valores por omisión para lo que no traiga."""
    datos = json.loads((directorio(slug) / "marca.json").read_text())
    datos.setdefault("slug", slug)
    datos.setdefault("limites", {})
    limites = {"titular": 60, "kicker": 28, "subtitulo": 90, "cta": 20, "url": 40}
    limites["disclaimer"] = 220
    datos["limites"] = {**limites, **datos["limites"]}
    datos.setdefault("plantillas", {})
    datos.setdefault("palabras_prohibidas", [])
    datos.setdefault("frases_trilladas", [])
    datos.setdefault("copy", {})
    datos["copy"].setdefault("max_caracteres", 900)
    datos["copy"].setdefault("max_lineas", 0)  # 0 = sin límite de líneas
    datos["copy"].setdefault("max_largo_linea", 0)
    datos["copy"].setdefault("emojis", True)
    datos.setdefault("imagen", {})
    datos["imagen"].setdefault("solo_titular", False)
    datos["imagen"].setdefault("tipos_con_extras", [])
    datos.setdefault("disclaimer_obligatorio", False)
    if not datos["plantillas"]:
        raise MarcaDesconocida(f"marcas/{slug}/marca.json no trae «plantillas»")
    return datos


def leer(slug: str, nombre: str) -> str:
    """Un archivo de texto de la marca (`ficha.md`, `ajustes.md`); "" si no existe."""
    ruta = directorio(slug) / nombre
    return ruta.read_text() if ruta.exists() else ""


def ficha(slug: str) -> str:
    texto = leer(slug, "ficha.md")
    if not texto.strip():
        raise MarcaDesconocida(f"marca sin ficha: {slug!r} (falta marcas/{slug}/ficha.md)")
    return texto


def archivos(slug: str, carpeta: str) -> list[Path]:
    """Archivos de `logos/` o `referencias/` (solo imágenes), ordenados."""
    base = directorio(slug) / carpeta
    if not base.exists():
        return []
    return sorted(
        p for p in base.iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")
    )
