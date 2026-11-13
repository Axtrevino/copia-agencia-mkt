"""Paid: Claude convierte lo que pide la persona («quiero leads en Monterrey, unos 250 al día»)
en una propuesta de campaña de Meta lista para aprobar en el panel.

La propuesta no crea nada: el panel la muestra y, con «Aprobar y crear en pausa», la manda al flujo
«Paid campañas», que redacta el anuncio, hace la pieza y la crea en Meta en pausa. Usa Claude
(`ANTHROPIC_API_KEY`); si no hay llave de Anthropic, usa GPT (`OPENAI_API_KEY`). Las reglas
(objetivos válidos, tope diario, landing del sitio de la marca) las aplica el código, no el modelo.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from collections.abc import Callable
from urllib.parse import urlparse

from app import marcas
from app.pieza import PedidoMalo
from app.research import ErrorHTTP, ficha_del_pedido

OBJETIVOS = {
    "leads_sitio": "que dejen sus datos en una página del sitio (píxel)",
    "leads_formulario": "que dejen sus datos en un formulario de Meta sin salir de FB o IG",
    "trafico": "que visiten una página del sitio",
    "reconocimiento": "que conozcan la marca (alcance)",
    "interaccion": "que interactúen con un post ya publicado",
    "seguidores_fb": "que den Me gusta a la página de Facebook",
    "visitas_ig": "que visiten el perfil de Instagram",
}
CON_SITIO = ("leads_sitio", "trafico")
TOPE = 300
MINIMO = 30
URL_ANTHROPIC = "https://api.anthropic.com/v1/messages"
URL_OPENAI = "https://api.openai.com/v1/chat/completions"

INSTRUCCIONES = """Eres el estratega de pauta de la marca descrita en la ficha. La persona te dice
con sus palabras qué campaña de Meta quiere; tú la conviertes en una propuesta concreta.

Devuelves SOLO un objeto JSON con:
- "nombre": nombre corto de la campaña (máximo 60 caracteres), p. ej. «Leads · CDMX y Monterrey».
- "objetivo": uno de {objetivos}.
- "presupuesto_diario": MXN al día, entero entre {minimo} y {tope}. Si la persona dio un monto,
  úsalo (si pasa del tope, pon el tope y dilo en "notas").
- "publico": a quién va, en una línea (rol, edad, lugares).
- "landing": URL https del sitio de la marca a donde lleva el anuncio (para leads_sitio y trafico;
  "" para los demás). Usa una página que exista según la ficha; si no sabes, la portada del sitio.
- "titular": titular del anuncio (máximo 60 caracteres), claro, sin juegos de palabras.
- "texto": texto del anuncio (máximo 280 caracteres) con la voz de la ficha.
- "mensaje": la idea del anuncio en una frase, para el redactor de la pieza.
- "notas": una línea para quien aprueba: por qué este objetivo y presupuesto.

Reglas: respeta la ficha (voz, palabras prohibidas, datos verificados); no inventes cifras ni
promesas. Si viene "anterior" y "cambios", corrige esa propuesta aplicando exactamente los cambios
y conserva lo demás. Objetivos posibles: {lista}"""


def _sitio(marca: str) -> str:
    cfg = marcas.config(marca)
    return (cfg.get("liga") or {}).get("sitio") or (cfg.get("blog") or {}).get("sitio") or ""


def _dominio(url: str) -> str:
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


def leer_propuesta(contenido, marca: str) -> dict:
    """Valida lo que devolvió el modelo y lo deja en la forma que pide el flujo «Paid campañas»."""
    if not isinstance(contenido, str):
        raise PedidoMalo("el modelo no devolvió texto")
    m = re.search(r"\{.*\}", contenido, re.S)
    try:
        p = json.loads(m.group(0) if m else contenido)
    except json.JSONDecodeError:
        raise PedidoMalo("el modelo no devolvió JSON válido") from None
    if not isinstance(p, dict):
        raise PedidoMalo("el modelo no devolvió un objeto JSON")
    objetivo = str(p.get("objetivo") or "")
    if objetivo not in OBJETIVOS:
        raise PedidoMalo(f"objetivo no válido: {objetivo!r}; usa uno de {', '.join(OBJETIVOS)}")
    try:
        presupuesto = round(float(p.get("presupuesto_diario")))
    except (TypeError, ValueError):
        raise PedidoMalo("presupuesto_diario debe ser un número") from None
    if not MINIMO <= presupuesto <= TOPE:
        raise PedidoMalo(f"presupuesto_diario debe estar entre {MINIMO} y {TOPE}")
    nombre = str(p.get("nombre") or "").strip()[:100]
    if not nombre:
        raise PedidoMalo("falta nombre")
    titular = str(p.get("titular") or "").strip()
    if len(titular) > 60:
        raise PedidoMalo(f"el titular tiene {len(titular)} caracteres; máximo 60")
    texto = str(p.get("texto") or "").strip()
    if len(texto) > 280:
        raise PedidoMalo(f"el texto tiene {len(texto)} caracteres; máximo 280")
    sitio = _sitio(marca)
    landing = str(p.get("landing") or "").strip()
    if landing and (not landing.startswith("https://") or _dominio(landing) != _dominio(sitio)):
        raise PedidoMalo(
            f"la landing debe ser una página https de {_dominio(sitio) or 'el sitio de la marca'}"
        )
    if objetivo in CON_SITIO and not landing:
        landing = sitio
    return {
        "marca": marca,
        "medio": "meta",
        "nombre": nombre,
        "objetivo": objetivo,
        "presupuesto_diario": presupuesto,
        "publico": str(p.get("publico") or "").strip()[:200],
        "landing": landing,
        "titular": titular,
        "texto": texto,
        "mensaje": str(p.get("mensaje") or nombre).strip()[:300],
        "notas": str(p.get("notas") or "").strip()[:300],
    }


def _http(url: str, cuerpo: dict, cabeceras: dict, timeout: int = 120) -> dict:
    req = urllib.request.Request(url, data=json.dumps(cuerpo).encode(), headers=cabeceras)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:  # el mensaje del proveedor no trae la llave
        raise RuntimeError(
            f"el modelo respondió {exc.code}: {exc.read()[:300].decode(errors='replace')}"
        ) from None


def preguntar_claude(sistema: str, usuario: str, llave: str, modelo: str) -> str:
    datos = _http(
        URL_ANTHROPIC,
        {
            "model": modelo,
            "max_tokens": 1500,
            "system": sistema,
            "messages": [{"role": "user", "content": usuario}],
        },
        {"x-api-key": llave, "anthropic-version": "2023-06-01", "content-type": "application/json"},
    )
    return "".join(b.get("text", "") for b in datos.get("content", []) if b.get("type") == "text")


def preguntar_gpt(sistema: str, usuario: str, llave: str, modelo: str) -> str:
    datos = _http(
        URL_OPENAI,
        {
            "model": modelo,
            "messages": [
                {"role": "system", "content": sistema},
                {"role": "user", "content": usuario},
            ],
            "response_format": {"type": "json_object"},
        },
        {"Authorization": f"Bearer {llave}", "Content-Type": "application/json"},
    )
    return datos["choices"][0]["message"]["content"]


def proponer(
    ficha: str,
    pedido: dict,
    preguntar: Callable[[str, str], str],
    intentos: int = 2,
) -> dict:
    """Pide la propuesta al modelo; si no cumple las reglas, le devuelve el error y reintenta."""
    marca = str(pedido.get("marca") or "")
    texto = str(pedido.get("texto") or "").strip()
    if not texto:
        raise PedidoMalo("escribe qué campaña quieres")
    sistema = INSTRUCCIONES.format(
        objetivos=", ".join(OBJETIVOS),
        minimo=MINIMO,
        tope=TOPE,
        lista="; ".join(f"{k}: {v}" for k, v in OBJETIVOS.items()),
    )
    sistema += f"\n\nSitio de la marca: {_sitio(marca)}\n\n# Ficha de la marca\n\n{ficha}"
    tarea = {"pide": texto}
    if isinstance(pedido.get("anterior"), dict):
        tarea["anterior"] = pedido["anterior"]
        tarea["cambios"] = texto
    usuario = json.dumps(tarea, ensure_ascii=False)
    error = ""
    for _ in range(intentos):
        respuesta = preguntar(
            sistema,
            usuario + (f"\n\nLa vez anterior no cumplió: {error}. Corrígelo." if error else ""),
        )
        try:
            return leer_propuesta(respuesta, marca)
        except PedidoMalo as exc:
            error = str(exc)
    raise PedidoMalo(f"no logré una propuesta válida: {error}")


def atender(
    pedido: dict, token: str | None, token_esperado: str | None, llaves: dict, modelos: dict
) -> dict:
    """Lógica de POST /campana: token y marca se revisan antes de gastar en el modelo."""
    from app.servicio import token_valido

    if not token_valido(token, token_esperado):
        raise ErrorHTTP(401, "token inválido")
    marca, ficha = ficha_del_pedido(pedido)
    if llaves.get("anthropic"):

        def preguntar(s, u):
            return preguntar_claude(s, u, llaves["anthropic"], modelos["claude"])

        quien = "Claude"
    elif llaves.get("openai"):

        def preguntar(s, u):
            return preguntar_gpt(s, u, llaves["openai"], modelos["gpt"])

        quien = "GPT"
    else:
        raise ErrorHTTP(502, "falta ANTHROPIC_API_KEY (o OPENAI_API_KEY) en el secret de Modal")
    try:
        propuesta = proponer(ficha, pedido, preguntar)
    except PedidoMalo as exc:
        raise ErrorHTTP(422, str(exc)) from None
    except RuntimeError as exc:
        raise ErrorHTTP(502, str(exc)) from None
    return {"ok": True, "marca": marca, "propuesta": propuesta, "modelo": quien}
