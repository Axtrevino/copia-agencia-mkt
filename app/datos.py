"""Datos verificados de la marca: la única fuente es la ficha (`marcas/<slug>/ficha.md`).

La sección «## Datos verificados» de la ficha trae líneas `- clave: valor` (precios, cifras,
fechas, el disclaimer legal si la marca lo necesita). Posts, artículos y la revisión de reglas los
leen de aquí; en el código no se escribe ninguna cifra de la marca. Si cambia un dato, se cambia
solo en la ficha. Solo librería estándar, sin red.
"""

from __future__ import annotations

import re

_SECCION_DATOS = re.compile(r"^##\s+Datos verificados.*?$(?P<cuerpo>.*?)(?=^##\s|\Z)", re.M | re.S)
_DATO = re.compile(r"^-\s+`?(?P<clave>[a-z_]+)`?\s*:\s*(?P<valor>.+?)\s*$", re.M)

# Tope para no inflar el prompt con los ajustes del dueño de la marca.
MAX_AJUSTES = 6000


def datos_verificados(ficha: str) -> dict[str, str]:
    """Lee la sección «## Datos verificados» de una ficha: líneas `- clave: valor`.

    Devuelve `{}` si la ficha no la trae.
    """
    m = _SECCION_DATOS.search(ficha or "")
    if not m:
        return {}
    return {d.group("clave"): d.group("valor") for d in _DATO.finditer(m.group("cuerpo"))}


def seccion(texto: str, titulo: str) -> str:
    """El cuerpo de la sección «## <titulo>» de un Markdown (sin el encabezado); "" si no está."""
    patron = rf"^##\s+{re.escape(titulo)}\s*$(?P<cuerpo>.*?)(?=^##\s|\Z)"
    m = re.search(patron, texto or "", re.M | re.S | re.I)
    return m.group("cuerpo").strip() if m else ""
