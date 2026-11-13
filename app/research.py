"""El agente de Research: GPT convierte lo que juntó n8n en hallazgos accionables.

n8n reúne por marca las noticias (Tavily), los anuncios de la competencia (Biblioteca de Anuncios
de Meta vía Apify) y las palabras clave (DataForSEO). Este módulo arma el pedido para GPT con la
ficha de la marca, valida la respuesta y reintenta una vez si no cumple. Solo librería estándar;
la llamada a OpenAI llega inyectada.
"""

from __future__ import annotations

import ipaddress
import json
import re
from collections.abc import Callable
from urllib.parse import urlparse

from app import marcas
from app.pieza import PedidoMalo
from app.redactor import _enviar_urllib

TIPOS = ("competencia", "anuncios", "keywords", "voz", "tendencias", "regulacion")
INTENCIONES = ("comercial", "informativa", "comparativa", "b2b")
MAX_RESUMEN = 900  # cabe en un mensaje de Telegram con su encabezado
MAX_HALLAZGOS = 12
MAX_ENTRADA = 60_000  # caracteres de datos crudos que se mandan a GPT

INSTRUCCIONES = """Eres el analista de research de la marca descrita en la ficha.
Recibes datos crudos de la semana: noticias, anuncios activos de la competencia y palabras clave
con volumen. También pueden venir "anteriores": hallazgos ya reportados que NO debes repetir. Si
viene "tema", enfoca el resumen y los hallazgos en ese tema.

Devuelves SOLO un objeto JSON con estas llaves:
- "resumen": máximo {max_resumen} caracteres, en español llano, para leer en el celular: lo más
  importante de la semana y qué conviene hacer. Sin markdown.
- "hallazgos": lista (máximo {max_hallazgos}) de objetos con
  "tipo" (uno de {tipos}), "hallazgo" (una o dos frases), "fuente" (URL de donde sale; "" si es
  inferencia), "accion" (qué hacer: contenido, anuncio, SEO o nada) y
  "confianza" ("dato" si la fuente lo dice tal cual, "inferencia" si es tu lectura).
- "keywords_nuevas": lista de objetos {{"keyword", "intencion", "prioridad"}} con intención en
  {intenciones} y prioridad 1 (alta) a 3 (baja). Solo palabras que valga la pena trabajar.

Reglas: no inventes cifras ni fuentes; cada "dato" lleva una URL que venga en los datos crudos.
Respeta las palabras prohibidas y las reglas de la ficha en las acciones que propones.
Si no hay nada nuevo, dilo en el resumen y deja las listas vacías."""


class ErrorHTTP(Exception):
    """Rechazo del endpoint con su código HTTP; main.py lo traduce a HTTPException."""

    def __init__(self, codigo: int, detalle: str):
        super().__init__(detalle)
        self.codigo = codigo
        self.detalle = detalle


def ficha_del_pedido(pedido) -> tuple[str, str]:
    """`(marca, ficha)` del pedido o `ErrorHTTP` 422 si la marca no existe."""
    if not isinstance(pedido, dict):
        raise ErrorHTTP(422, "el cuerpo debe ser un objeto JSON")
    marca = str(pedido.get("marca") or "")
    try:
        return marca, marcas.ficha(marca)
    except marcas.MarcaDesconocida as exc:
        raise ErrorHTTP(422, str(exc)) from None


def armar_mensajes(ficha: str, pedido: dict) -> list[dict]:
    sistema = INSTRUCCIONES.format(
        max_resumen=MAX_RESUMEN,
        max_hallazgos=MAX_HALLAZGOS,
        tipos=", ".join(TIPOS),
        intenciones=", ".join(INTENCIONES),
    )
    datos = {
        k: pedido.get(k)
        for k in ("marca", "semana", "tema", "datos", "anteriores")
        if pedido.get(k)
    }
    crudo = json.dumps(datos, ensure_ascii=False)
    if len(crudo) > MAX_ENTRADA:
        crudo = crudo[:MAX_ENTRADA] + " …(recortado)"
    return [
        {"role": "system", "content": f"{sistema}\n\n# Ficha de la marca\n\n{ficha}"},
        {"role": "user", "content": f"Datos de la semana:\n{crudo}"},
    ]


ETIQUETA = re.compile(r"[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?")


def host_valido(host: str) -> bool:
    """Dominio DNS (también internacional, vía IDNA) o dirección IP."""
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        pass
    try:
        ascii_host = host.encode("idna").decode("ascii").lower()
    except UnicodeError:
        return False
    etiquetas = ascii_host.rstrip(".").split(".")
    return len(etiquetas) >= 2 and all(ETIQUETA.fullmatch(e) for e in etiquetas)


def es_url(texto: str) -> bool:
    """URL HTTP(S) que se puede abrir: esquema, servidor válido, puerto numérico, sin espacios."""
    if any(c.isspace() or ord(c) < 32 for c in texto):
        return False
    try:
        partes = urlparse(texto)
        partes.port  # noqa: B018 — lanza ValueError si el puerto no es numérico
    except ValueError:
        return False
    return partes.scheme in ("http", "https") and host_valido(partes.hostname or "")


def texto(valor, campo: str, requerido: bool = True) -> str:
    """El campo debe ser texto; los objetos o listas no se convierten a cadena."""
    if valor is None and not requerido:
        return ""
    if not isinstance(valor, str):
        raise PedidoMalo(f"«{campo}» debe ser texto")
    limpio = valor.strip()
    if requerido and not limpio:
        raise PedidoMalo(f"falta «{campo}»")
    return limpio


def fuentes_de(datos) -> set[str]:
    """URLs que vienen en los datos crudos: las únicas que valen como fuente de un dato."""
    encontradas: set[str] = set()
    pendientes = [datos]
    while pendientes:
        actual = pendientes.pop()
        if isinstance(actual, dict):
            pendientes.extend(actual.values())
        elif isinstance(actual, list):
            pendientes.extend(actual)
        elif isinstance(actual, str) and es_url(actual.strip()):
            encontradas.add(actual.strip())
    return encontradas


def lista_de_objetos(valor, nombre: str) -> list[dict]:
    if not isinstance(valor, list) or not all(isinstance(v, dict) for v in valor):
        raise PedidoMalo(f"«{nombre}» debe ser una lista de objetos")
    return valor


def leer_reporte(contenido: str, fuentes: set[str] | None = None) -> dict:
    """Valida el JSON de GPT: resumen corto, tipos conocidos y fuentes en los datos."""
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
    hallazgos = []
    crudos = lista_de_objetos(rep.get("hallazgos"), "hallazgos")
    if len(crudos) > MAX_HALLAZGOS:
        raise PedidoMalo(f"son {len(crudos)} hallazgos; el máximo es {MAX_HALLAZGOS}")
    for h in crudos:
        tipo = h.get("tipo")
        if tipo not in TIPOS:
            raise PedidoMalo(f"tipo de hallazgo desconocido: {tipo!r}")
        hallazgo = texto(h.get("hallazgo"), "hallazgo")
        fuente = texto(h.get("fuente"), "fuente", requerido=False)
        accion = texto(h.get("accion"), "accion")
        confianza = h.get("confianza")
        if confianza not in ("dato", "inferencia"):
            raise PedidoMalo(f'«confianza» debe ser "dato" o "inferencia": {confianza!r}')
        if confianza == "dato" and not es_url(fuente):
            raise PedidoMalo(f"el dato «{hallazgo[:40]}» no trae una URL de fuente válida")
        if confianza == "dato" and fuentes is not None and fuente not in fuentes:
            raise PedidoMalo(f"la fuente {fuente} no viene en los datos; usa una de ellos")
        hallazgos.append(
            {
                "tipo": tipo,
                "hallazgo": hallazgo,
                "fuente": fuente,
                "accion": accion,
                "confianza": confianza,
            }
        )
    keywords = []
    for k in lista_de_objetos(rep.get("keywords_nuevas"), "keywords_nuevas"):
        palabra = texto(k.get("keyword"), "keyword").lower()
        intencion = k.get("intencion")
        if intencion not in INTENCIONES:
            raise PedidoMalo(f"intención desconocida para «{palabra}»: {intencion!r}")
        prioridad = k.get("prioridad")
        if isinstance(prioridad, bool) or prioridad not in (1, 2, 3):
            raise PedidoMalo(f"la prioridad de «{palabra}» debe ser 1, 2 o 3")
        keywords.append({"keyword": palabra, "intencion": intencion, "prioridad": prioridad})
    return {"resumen": resumen, "hallazgos": hallazgos, "keywords_nuevas": keywords}


def pedir_json(
    mensajes: list[dict],
    leer: Callable[[str | None], dict],
    llave: str,
    modelo: str,
    enviar: Callable[[dict, str], dict],
    intentos: int = 2,
) -> dict:
    """Pide JSON a GPT y lo valida con `leer`; si no cumple, le devuelve el error y reintenta."""
    if not llave:
        raise RuntimeError("falta OPENAI_API_KEY en el secret de Modal")
    error = ""
    for _ in range(intentos):
        datos = enviar(
            {"model": modelo, "messages": mensajes, "response_format": {"type": "json_object"}},
            llave,
        )
        try:
            contenido = datos["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            contenido = None  # sin texto: cuenta como respuesta que no cumple y se reintenta
        try:
            salida = leer(contenido)
        except PedidoMalo as exc:
            error = str(exc)
            mensajes = mensajes + [
                {"role": "assistant", "content": contenido if isinstance(contenido, str) else ""},
                {"role": "user", "content": f"No cumple las reglas: {error}. Corrígelo."},
            ]
            continue
        salida["modelo"] = modelo
        salida["uso"] = (datos.get("usage") if isinstance(datos, dict) else None) or {}
        return salida
    raise PedidoMalo(f"GPT no logró una respuesta válida: {error}")


def sintetizar(
    ficha: str,
    pedido: dict,
    llave: str,
    modelo: str = "gpt-5.5",
    enviar: Callable[[dict, str], dict] = _enviar_urllib,
) -> dict:
    fuentes = fuentes_de(pedido.get("datos"))
    return pedir_json(
        armar_mensajes(ficha, pedido), lambda c: leer_reporte(c, fuentes), llave, modelo, enviar
    )


def atender(
    pedido: dict,
    token: str | None,
    token_esperado: str | None,
    llave: str,
    modelo: str = "gpt-5.5",
    enviar: Callable[[dict, str], dict] = _enviar_urllib,
) -> dict:
    """Lógica de POST /research: token y ficha se revisan antes de gastar en GPT."""
    from app.servicio import token_valido

    if not token_valido(token, token_esperado):
        raise ErrorHTTP(401, "token inválido")
    marca, ficha = ficha_del_pedido(pedido)
    try:
        reporte = sintetizar(ficha, pedido, llave, modelo=modelo, enviar=enviar)
    except PedidoMalo as exc:
        raise ErrorHTTP(422, str(exc)) from None
    except RuntimeError as exc:
        raise ErrorHTTP(502, str(exc)) from None
    return {"marca": marca, **reporte}
