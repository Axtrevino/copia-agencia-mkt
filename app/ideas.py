"""Agente de ideas: GPT escribe el `tema` (brief creativo) de cada post de la semana.

Cada semana, después del Research, n8n manda por marca los posts `planeado` sin tema, los
hallazgos recientes (competencia, voz del cliente, tendencias, regulación), lo que dice el público
en foros y noticias (Tavily) y lo ya publicado. Este módulo agrega el calendario de temporadas,
pide a GPT un ángulo distinto por post y valida que cada idea venga de una fuente real. Sin
seguidores ni pauta, las métricas no dicen nada: las ideas salen de competencia, temporada y
público. Solo librería estándar; la llamada a OpenAI llega inyectada.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date

from app import marcas
from app.pieza import PedidoMalo
from app.redactor import _enviar_urllib
from app.research import (
    ErrorHTTP,
    es_url,
    ficha_del_pedido,
    fuentes_de,
    lista_de_objetos,
    pedir_json,
    texto,
)
from app.temporada import alrededor

FUENTES = ("competencia", "temporada", "target")
MAX_TEMA = 600
MAX_RESUMEN = 700
MAX_POSTS = 12
MAX_ENTRADA = 60_000

INSTRUCCIONES = """Eres el estratega creativo de redes sociales de la marca descrita en la ficha.
Tu trabajo es que cada post tenga una idea con filo, anclada en algo real que esté pasando, y no
contenido predecible o genérico.

Recibes:
- "posts": los posts por llenar (post_id, fecha, tipo y, a veces, "tema_previo"). Respeta el
  "tipo". "tema_previo" es una idea vieja del calendario, casi siempre genérica: úsala solo como
  pista de la ocasión y reescríbela con filo.
- "temporada": fechas y temporadas cerca de cada post.
- "hallazgos": lo que encontró el Research (anuncios de la competencia, voz del cliente,
  tendencias, regulación), con su fuente.
- "voz": lo que dice el público objetivo en foros, reseñas y noticias, con su URL.
- "publicados": lo que ya salió o ya está escrito. NO repitas sus ideas, ganchos ni escenas.

Devuelves SOLO un objeto JSON con:
- "resumen": máximo {max_resumen} caracteres, en español llano para leer en el celular: el hilo
  de la semana y por qué estas ideas. Sin markdown.
- "ideas": una por cada post, objetos con
  "post_id" (tal cual), "fuente_tipo" (uno de {fuentes}), "fuente" (URL de los datos de donde
  sale; "" si viene del calendario de temporada sin URL) y "tema" (máximo {max_tema}
  caracteres) con este formato exacto:
  "Insight: <la tensión real, en palabras del público> | Ángulo: <la toma no obvia> | Gancho:
  <primera línea propuesta> | Por qué ahora: <qué pasa esta semana>".

Reglas:
- Varía la fuente: si hay 3 o más posts, usa al menos dos tipos de fuente distintos, y que no
  todos salgan de la temporada.
- Competencia: toma lo que la competencia dice o promete y busca el contraste honesto (lo que no
  dice, lo que el público se queja de ella). Nunca nombres a la competencia en el post.
- Público: usa sus palabras, sus dudas y sus quejas concretas, no categorías abstractas.
- Prohibido lo genérico: tips obvios, frases de catálogo, escenas de banco de imágenes.{trilladas}
- No inventes cifras, montos, testimonios ni fuentes. Respeta las palabras prohibidas y las
  reglas de la ficha.
- Dos ideas de la misma semana no pueden compartir insight ni gancho."""


def _fecha(valor) -> date | None:
    try:
        return date.fromisoformat(str(valor)[:10])
    except ValueError:
        return None


def temporada_de(posts: list[dict], cfg: dict | None = None) -> list[dict]:
    """Eventos de temporada alrededor de las fechas de los posts, sin repetir."""
    cfg = cfg or {}
    vistos: dict[tuple, dict] = {}
    for p in posts:
        f = _fecha(p.get("fecha"))
        if not f:
            continue
        for e in alrededor(f, propias=cfg.get("temporadas"), quincenas=bool(cfg.get("quincenas"))):
            vistos.setdefault((e["inicio"], e["nombre"]), e)
    return sorted(vistos.values(), key=lambda e: (e["inicio"], e["nombre"]))


def leer_posts(pedido: dict) -> list[dict]:
    crudos = pedido.get("posts")
    if not isinstance(crudos, list) or not crudos:
        raise PedidoMalo("faltan «posts» por llenar")
    if len(crudos) > MAX_POSTS:
        raise PedidoMalo(f"son {len(crudos)} posts; el máximo es {MAX_POSTS}")
    posts, ids = [], set()
    for p in lista_de_objetos(crudos, "posts"):
        post_id = texto(p.get("post_id"), "post_id")
        if post_id in ids:
            raise PedidoMalo(f"post_id repetido: {post_id}")
        ids.add(post_id)
        posts.append(
            {
                "post_id": post_id,
                "fecha": str(p.get("fecha") or ""),
                "tipo": str(p.get("tipo") or ""),
            }
        )
        previo = str(p.get("tema_previo") or "").strip()[:300]
        if previo:
            posts[-1]["tema_previo"] = previo
    return posts


def armar_mensajes(ficha: str, pedido: dict, posts: list[dict], cfg: dict) -> list[dict]:
    trilladas = ""
    if cfg.get("frases_trilladas"):
        trilladas = " También: " + ", ".join(f'"{f}"' for f in cfg["frases_trilladas"]) + "."
    sistema = INSTRUCCIONES.format(
        max_resumen=MAX_RESUMEN, max_tema=MAX_TEMA, fuentes=", ".join(FUENTES), trilladas=trilladas
    )
    datos = {
        "marca": pedido.get("marca"),
        "posts": posts,
        "temporada": temporada_de(posts, cfg),
        "hallazgos": pedido.get("hallazgos") or [],
        "voz": pedido.get("voz") or [],
        "publicados": pedido.get("publicados") or [],
    }
    crudo = json.dumps(datos, ensure_ascii=False)
    if len(crudo) > MAX_ENTRADA:
        crudo = crudo[:MAX_ENTRADA] + " …(recortado)"
    return [
        {"role": "system", "content": f"{sistema}\n\n# Ficha de la marca\n\n{ficha}"},
        {"role": "user", "content": f"Datos de la semana:\n{crudo}"},
    ]


def leer_ideas(contenido, posts: list[dict], fuentes: set[str]) -> dict:
    """Valida el JSON de GPT: una idea por post, fuentes reales y variedad de fuentes."""
    if not isinstance(contenido, str):
        raise PedidoMalo("GPT no devolvió texto")
    try:
        rep = json.loads(contenido)
    except json.JSONDecodeError:
        raise PedidoMalo("GPT no devolvió JSON válido") from None
    if not isinstance(rep, dict):
        raise PedidoMalo("GPT no devolvió un objeto JSON")
    resumen = texto(rep.get("resumen"), "resumen")
    if len(resumen) > MAX_RESUMEN:
        raise PedidoMalo(f"el resumen tiene {len(resumen)} caracteres; el máximo es {MAX_RESUMEN}")
    esperados = [p["post_id"] for p in posts]
    ideas, vistos, temas = [], set(), set()
    for i in lista_de_objetos(rep.get("ideas"), "ideas"):
        post_id = texto(i.get("post_id"), "post_id")
        if post_id not in esperados:
            raise PedidoMalo(f"post_id desconocido: {post_id}")
        if post_id in vistos:
            raise PedidoMalo(f"dos ideas para {post_id}")
        vistos.add(post_id)
        tipo = i.get("fuente_tipo")
        if tipo not in FUENTES:
            raise PedidoMalo(f"fuente_tipo desconocido en {post_id}: {tipo!r}")
        fuente = texto(i.get("fuente"), "fuente", requerido=False)
        if fuente and (not es_url(fuente) or fuente not in fuentes):
            raise PedidoMalo(f"la fuente de {post_id} no viene en los datos: {fuente}")
        if tipo != "temporada" and not fuente:
            raise PedidoMalo(f"la idea de {post_id} ({tipo}) necesita la URL de su fuente")
        tema = texto(i.get("tema"), "tema")
        if len(tema) > MAX_TEMA:
            raise PedidoMalo(
                f"el tema de {post_id} tiene {len(tema)} caracteres; máximo {MAX_TEMA}"
            )
        for parte in ("Insight:", "Ángulo:", "Gancho:", "Por qué ahora:"):
            if parte not in tema:
                raise PedidoMalo(f"al tema de {post_id} le falta «{parte}»")
        clave = tema.split("| Ángulo:", 1)[0].strip().lower()
        if clave in temas:
            raise PedidoMalo(f"el insight de {post_id} repite el de otro post")
        temas.add(clave)
        ideas.append({"post_id": post_id, "fuente_tipo": tipo, "fuente": fuente, "tema": tema})
    faltan = [p for p in esperados if p not in vistos]
    if faltan:
        raise PedidoMalo(f"faltan ideas para: {', '.join(faltan)}")
    tipos = {i["fuente_tipo"] for i in ideas}
    if len(ideas) >= 3 and (len(tipos) < 2 or tipos == {"temporada"}):
        raise PedidoMalo("usa al menos dos tipos de fuente distintos (no solo temporada)")
    orden = {p: n for n, p in enumerate(esperados)}
    ideas.sort(key=lambda i: orden[i["post_id"]])
    return {"resumen": resumen, "ideas": ideas}


def proponer(
    ficha: str,
    pedido: dict,
    llave: str,
    modelo: str = "gpt-5.5",
    enviar: Callable[[dict, str], dict] = _enviar_urllib,
) -> dict:
    cfg = marcas.config(str(pedido.get("marca") or ""))
    posts = leer_posts(pedido)
    fuentes = fuentes_de([pedido.get("hallazgos"), pedido.get("voz"), temporada_de(posts, cfg)])
    return pedir_json(
        armar_mensajes(ficha, pedido, posts, cfg),
        lambda c: leer_ideas(c, posts, fuentes),
        llave,
        modelo,
        enviar,
    )


def atender(
    pedido: dict,
    token: str | None,
    token_esperado: str | None,
    llave: str,
    modelo: str = "gpt-5.5",
    enviar: Callable[[dict, str], dict] = _enviar_urllib,
) -> dict:
    """Lógica de POST /ideas: token, ficha y posts se revisan antes de gastar en GPT."""
    from app.servicio import token_valido

    if not token_valido(token, token_esperado):
        raise ErrorHTTP(401, "token inválido")
    marca, ficha = ficha_del_pedido(pedido)
    try:
        rep = proponer(ficha, pedido, llave, modelo=modelo, enviar=enviar)
    except PedidoMalo as exc:
        raise ErrorHTTP(422, str(exc)) from None
    except RuntimeError as exc:
        raise ErrorHTTP(502, str(exc)) from None
    return {"marca": marca, **rep}
