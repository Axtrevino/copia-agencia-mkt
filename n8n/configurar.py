"""Llena los marcadores (__ASI__) de los flujos con tus valores y los deja listos para importar.

Uso (desde la raíz del repo):
    cp n8n/config.ejemplo.json n8n/config.json   # y llénalo
    python3 n8n/configurar.py

Resultado: n8n/listos/*.json. Cada flujo lleva un ID fijo y las referencias entre flujos (alertas,
sub-flujos) ya apuntan a esos IDs. Si importas con la línea de comandos de n8n
(`n8n import:workflow --separate --input=n8n/listos`) los IDs se respetan. Si importas desde la
pantalla de n8n, n8n les pone IDs nuevos: entonces corre `python3 n8n/configurar.py --ids` después
para ver qué nodos debes reconectar a mano (README → «Importar desde la pantalla»).
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
FLUJOS = AQUI / "flujos"
LISTOS = AQUI / "listos"
NUMEROS = ("TEMA_APROBACIONES", "TEMA_REPORTES", "TEMA_ALERTAS")

# Referencias entre flujos: marcador → archivo del flujo al que apunta.
REFERENCIAS = {
    "FLUJO_ALERTAS": "01-alertas-de-error.json",
    "FLUJO_PUBLICAR_A": "11-publicar-posts-marca-a.json",
    "FLUJO_PUBLICAR_B": "11-publicar-posts-marca-b.json",
    "FLUJO_NUEVA_VERSION": "13-nueva-version-de-post.json",
    "FLUJO_SEO_BORRADORES": "40-seo-borradores.json",
    "FLUJO_SEO_ACCIONES": "41-seo-acciones.json",
}


def id_de(archivo: str) -> str:
    """ID estable de 16 caracteres para un flujo (n8n usa ese formato)."""
    return hashlib.sha1(archivo.encode()).hexdigest()[:16]


def main() -> int:
    ruta = AQUI / "config.json"
    if not ruta.exists():
        print("Falta n8n/config.json (copia config.ejemplo.json y llénalo).")
        return 1
    config = {k: v for k, v in json.loads(ruta.read_text()).items() if not k.startswith("_")}
    for k, archivo in REFERENCIAS.items():
        config[k] = id_de(archivo)
    LISTOS.mkdir(exist_ok=True)
    pendientes = set()
    for archivo in sorted(FLUJOS.glob("*.json")):
        texto = archivo.read_text()
        for k in NUMEROS:
            if k in config:
                texto = texto.replace(f'"__{k}__"', str(int(config[k])))
        for k, v in config.items():
            texto = texto.replace(f"__{k}__", str(v).replace('"', '\\"'))
        datos = json.loads(texto)
        datos["id"] = id_de(archivo.name)
        faltan = set(re.findall(r"__([A-Z0-9_]+)__", texto)) - {"HASH", "IGMEDIA"}
        pendientes |= faltan
        (LISTOS / archivo.name).write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n")
    print(f"Listos {len(list(LISTOS.glob('*.json')))} flujos en {LISTOS}")
    if pendientes:
        print("Ojo, faltan estos valores en config.json:", ", ".join(sorted(pendientes)))
    return 0


def ids() -> None:
    print("Si importaste desde la pantalla, reconecta estos nodos al flujo correcto («From list»):")
    for archivo in sorted(FLUJOS.glob("*.json")):
        texto = archivo.read_text()
        datos = json.loads(texto)
        for n in datos["nodes"]:
            s = json.dumps(n.get("parameters", {}))
            for k, destino in REFERENCIAS.items():
                if f"__{k}__" in s:
                    print(f"  {datos['name']} → nodo «{n['name']}» → {destino}")
        if "__FLUJO_ALERTAS__" in json.dumps(datos.get("settings", {})):
            print(f"  {datos['name']} → Settings → Error workflow → Agencia · Alertas de error")


if __name__ == "__main__":
    if "--ids" in sys.argv:
        ids()
        sys.exit(0)
    sys.exit(main())
