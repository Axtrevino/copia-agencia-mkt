"""El redactor SEO: GPT arma el brief y el borrador de un artículo de blog para una marca.

Con la ficha de la marca, GPT propone título, slug, meta descripción, brief, cuerpo HTML y FAQ.
Este módulo valida la respuesta y reintenta una vez si no cumple. Solo librería estándar; la
llamada a OpenAI llega inyectada. El artículo no se publica: queda como borrador para aprobar.

Todo lo de la marca sale de `marca.json` → `blog` (rol del redactor, reglas, fuentes oficiales
que puede citar) y de la ficha. Si la marca tiene `disclaimer_obligatorio`, todo artículo termina
con el disclaimer de «Datos verificados»: si GPT no lo puso, lo agrega el código.

Calidad: Google no castiga que un texto se escriba con IA, castiga el contenido sin valor. Por eso
cada artículo:
- cita al menos `MIN_FUENTES` fuentes con liga: las del pedido o las de `fuentes_oficiales` de la
  marca (URLs revisadas a mano; GPT no puede inventar rutas dentro de sitios oficiales);
- declara en «valor_unico» qué aporta que no tenga otro blog (ejemplo, tabla, lista, simulador);
- lleva al final, puesto por el código, la lista de fuentes y la firma: equipo editorial de la
  marca, el revisor (línea `revisor:` de «Datos verificados» de la ficha o «revisor» del pedido;
  nunca se inventa un nombre) y la fecha de actualización;
- regresa un reporte «calidad» con avisos para el aprobador (no bloquean).
"""

from __future__ import annotations

import html
import json
import re
import unicodedata
from collections.abc import Callable
from datetime import date, datetime
from html.parser import HTMLParser
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from app import marcas
from app.datos import datos_verificados
from app.pieza import PedidoMalo
from app.redactor import _enviar_urllib
from app.reglas import revisar
from app.research import ErrorHTTP, es_url, ficha_del_pedido, texto

INTENCIONES = ("informativa", "comercial", "comparativa", "b2b")
ETIQUETAS = {
    "h2",
    "h3",
    "p",
    "ul",
    "ol",
    "li",
    "strong",
    "em",
    "a",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
}

MAX_TITULO = 60
MAX_META = 155
MAX_SLUG = 60
MIN_PALABRAS = 800
MAX_PALABRAS = 2500
MIN_H2 = 3
MAX_H2 = 8
MIN_FUENTES = 2
MIN_FAQ = 3

# Fuentes oficiales generales que el redactor puede citar sin que vengan en el pedido. Solo URLs
# exactas y estables: una ruta inventada dentro de un sitio oficial da 404 y le quita confianza al
# artículo. Las de la industria de cada marca van en `marca.json` → `blog.fuentes_oficiales`.
FUENTES_GENERALES = {
    "https://www.dof.gob.mx/": "Diario Oficial de la Federación",
    "https://www.inegi.org.mx/": "INEGI",
    "https://www.gob.mx/profeco": "PROFECO",
}

MESES = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)

ROL_POR_OMISION = """Eres el redactor SEO del blog de {nombre}. Escribes para su público objetivo
(ver la ficha), claro y sin tecnicismos. Es contenido para el sitio, no un anuncio."""


def blog_de(marca: str) -> dict:
    """Configuración del blog de la marca: nombre, dominio, rol, reglas y fuentes oficiales."""
    cfg = marcas.config(marca)
    blog = dict(cfg.get("blog") or {})
    sitio = blog.get("sitio") or (cfg.get("liga") or {}).get("sitio") or ""
    dominio = (urlparse(sitio).hostname or "").lower().removeprefix("www.")
    if not dominio:
        raise PedidoMalo(f"la marca {marca} no trae «blog.sitio» ni «liga.sitio» en marca.json")
    nombre = cfg.get("nombre") or marca
    return {
        "nombre": nombre,
        "dominio": dominio,
        "rol": blog.get("rol") or ROL_POR_OMISION.format(nombre=nombre),
        "reglas": blog.get("reglas") or "- Respeta la ficha al pie de la letra.",
        "fuentes": {**FUENTES_GENERALES, **(blog.get("fuentes_oficiales") or {})},
        "disclaimer_obligatorio": bool(cfg["disclaimer_obligatorio"]),
    }


def _lista_fuentes_oficiales(fuentes: dict) -> str:
    return "\n".join(f"  - {url} ({nombre})" for url, nombre in fuentes.items())


def instrucciones(marca: str, datos: dict | None = None) -> str:
    cfg = blog_de(marca)
    disclaimer = str((datos or {}).get("disclaimer") or "").strip()
    extra = ""
    if cfg["disclaimer_obligatorio"] and disclaimer:
        extra = (
            "\n- El cuerpo termina con este texto exacto (si falta, el sistema lo agrega): "
            f"«{disclaimer}»"
        )
    return f"""{cfg["rol"]}

Escribe el brief y el borrador completo de un artículo de blog. Devuelves SOLO un objeto JSON con
estas llaves:
- "titulo": máximo {MAX_TITULO} caracteres. Debe incluir la keyword o, si no cabe, déjala para el
  primer h2.
- "slug": minúsculas ASCII y guiones, máximo {MAX_SLUG} caracteres. No es una URL completa.
- "meta_descripcion": máximo {MAX_META} caracteres, atractiva para el buscador.
- "brief": objeto con "intencion" (una de {", ".join(INTENCIONES)}), "h2s" (lista de los
  subtítulos h2 planeados) y "preguntas" (lista de preguntas que el artículo responderá).
- "cuerpo_html": el texto completo en HTML, entre {MIN_PALABRAS} y {MAX_PALABRAS} palabras, de
  {MIN_H2} a {MAX_H2} secciones h2. Usa SOLO estas etiquetas:
  {", ".join(sorted(ETIQUETAS))}.
  Nada de script, style, iframe ni atributos on*. La keyword debe aparecer en el título o en el
  primer h2.
- "faq": lista de al menos {MIN_FAQ} objetos con "pregunta" y "respuesta".
- "valor_unico": una línea: qué aporta este artículo que no tenga otro blog (el ejemplo paso a
  paso, la tabla, la lista de verificación o el simulador que incluiste).
- "notas": una línea breve para el aprobador: qué ángulo tomaste y por qué.

Calidad (Google premia el contenido útil y confiable; no basta con estar bien posicionado):
- Responde la duda del lector desde el primer párrafo. Nada de relleno, introducciones genéricas
  ni repetir la keyword de más.
- Cita al menos {MIN_FUENTES} fuentes distintas con <a href> dentro del texto, junto a la
  afirmación que respaldan. Usa solo URLs de "fuentes" del pedido o de esta lista de fuentes
  oficiales, copiadas tal cual (no inventes rutas dentro de esos sitios):
{_lista_fuentes_oficiales(cfg["fuentes"])}
- Si citas una ley, di el número de artículo y la ley solo si estás seguro de que existe y dice
  eso; si no, cita la ley en general.
- Incluye algo práctico que el lector pueda usar: un ejemplo paso a paso, una tabla comparativa
  o una lista de verificación. Si en "enlaces_internos" viene un simulador o calculadora,
  enlázalo donde ayude.
- No inventes testimonios, casos, clientes, nombres ni estadísticas.
- No firmes el artículo ni pongas fecha ni una sección de fuentes al final: el sistema agrega la
  lista de fuentes, la firma y la fecha de actualización.

Reglas de marca:
{cfg["reglas"]}{extra}
- Cada enlace <a href> debe apuntar a {cfg["dominio"]}, a una URL que venga en
  "enlaces_internos" o en "fuentes" del pedido, o a una de las fuentes oficiales de arriba. No
  inventes dominios ni uses la misma URL dos veces como si fueran fuentes distintas.
- Si el pedido trae "publicados", no repitas esos títulos ni propongas un ángulo idéntico."""


def _plegar_ascii(valor: str) -> str:
    """Minúsculas y sin acentos; preserva la ñ como n para el slug y la comparación."""
    valor = valor.replace("ñ", "n").replace("Ñ", "N")
    return unicodedata.normalize("NFKD", valor).encode("ascii", "ignore").decode("ascii").lower()


def _contiene(aguja: str, pajar: str) -> bool:
    return _plegar_ascii(aguja) in _plegar_ascii(pajar)


def normalizar_slug(titulo: str) -> str:
    """De «Guía de compras 2027» a `guia-de-compras-2027`; solo ASCII, minúsculas y guiones."""
    slug = re.sub(r"[^a-z0-9]+", "-", _plegar_ascii(titulo.strip())).strip("-")
    if not slug:
        return "articulo"
    return slug[:MAX_SLUG].rstrip("-") or "articulo"


def _lista_texto(valor, nombre: str, requerida: bool = False) -> list[str]:
    if valor is None:
        if requerida:
            raise PedidoMalo(f"falta «{nombre}»")
        return []
    if not isinstance(valor, list) or not all(isinstance(v, str) for v in valor):
        raise PedidoMalo(f"«{nombre}» debe ser una lista de texto")
    return [v.strip() for v in valor if v.strip()]


def _lista_objetos(valor, nombre: str) -> list[dict]:
    if not isinstance(valor, list) or not all(isinstance(v, dict) for v in valor):
        raise PedidoMalo(f"«{nombre}» debe ser una lista de objetos")
    return valor


def _marca(pedido: dict) -> str:
    marca = str(pedido.get("marca") or "")
    try:
        marcas.config(marca)
    except marcas.MarcaDesconocida as exc:
        raise PedidoMalo(str(exc)) from None
    return marca


def _datos_pedido(pedido: dict) -> dict:
    if not isinstance(pedido, dict):
        raise PedidoMalo("el cuerpo debe ser un objeto JSON")
    tema = texto(pedido.get("tema"), "tema")
    keyword = texto(pedido.get("keyword"), "keyword")
    intencion = pedido.get("intencion")
    if intencion is not None:
        if not isinstance(intencion, str):
            raise PedidoMalo("«intencion» debe ser texto")
        intencion = intencion.strip().lower()
        if intencion not in INTENCIONES:
            raise PedidoMalo(
                f"intención desconocida: {intencion!r}; usa una de {', '.join(INTENCIONES)}"
            )
    return {
        "marca": _marca(pedido),
        "tema": tema,
        "keyword": keyword,
        "intencion": intencion,
        "fuentes": _lista_texto(pedido.get("fuentes"), "fuentes"),
        "enlaces_internos": _lista_texto(pedido.get("enlaces_internos"), "enlaces_internos"),
        "publicados": _lista_texto(pedido.get("publicados"), "publicados"),
        "revisor": texto(pedido.get("revisor"), "revisor", requerido=False),
    }


def datos_de_marca(marca: str, ficha: str) -> dict:
    """«Datos verificados» de la ficha; si la marca exige disclaimer y no está, no se escribe."""
    datos = datos_verificados(ficha)
    if blog_de(marca)["disclaimer_obligatorio"] and not str(datos.get("disclaimer") or "").strip():
        raise RuntimeError(f"la ficha de {marca} no trae «disclaimer» en «Datos verificados»")
    return datos


def revisor_de(ficha: str, pedido: dict | None = None) -> str:
    """Quién revisa: «revisor» del pedido o la línea `revisor:` de «Datos verificados»."""
    del_pedido = (pedido or {}).get("revisor")
    if isinstance(del_pedido, str) and del_pedido.strip():
        return del_pedido.strip()
    return datos_verificados(ficha).get("revisor", "").strip()


def armar_mensajes(ficha: str, pedido: dict) -> list[dict]:
    datos = _datos_pedido(pedido)
    verificados = datos_de_marca(datos["marca"], ficha)
    tarea: dict[str, object] = {"tema": datos["tema"], "keyword": datos["keyword"]}
    for campo in ("intencion", "fuentes", "enlaces_internos", "publicados"):
        if datos[campo]:
            tarea[campo] = datos[campo]
    return [
        {
            "role": "system",
            "content": (
                f"{instrucciones(datos['marca'], verificados)}\n\n# Ficha de la marca\n\n{ficha}"
            ),
        },
        {
            "role": "user",
            "content": f"Datos del artículo:\n{json.dumps(tarea, ensure_ascii=False, indent=2)}",
        },
    ]


class _AnalizadorHTML(HTMLParser):
    """Extrae texto, cuenta palabras, junta h2 y valida etiquetas/atributos/hrefs."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.error: str | None = None
        self.h2s: list[str] = []
        self.hrefs: list[str] = []
        self.etiquetas: set[str] = set()
        self._partes: list[str] = []
        self._en_h2 = False
        self._h2_parte: list[str] = []

    def _revisar(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in ETIQUETAS:
            self.error = f"etiqueta no permitida: <{tag}>"
            return
        self.etiquetas.add(tag)
        for nombre, _ in attrs:
            if nombre.lower().startswith("on"):
                self.error = f"atributo no permitido: {nombre}"
                return
        if tag == "a":
            hrefs = [valor or "" for nombre, valor in attrs if nombre.lower() == "href"]
            if len(hrefs) != 1:
                self.error = "cada <a> debe llevar exactamente un href"
                return
            self.hrefs.append(hrefs[0])

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.error:
            return
        self._revisar(tag, attrs)
        if tag == "h2":
            self._en_h2 = True
            self._h2_parte = []

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.error:
            return
        self._revisar(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if tag == "h2" and self._en_h2:
            self._en_h2 = False
            self.h2s.append(_normalizar_espacios("".join(self._h2_parte)))

    def handle_data(self, data: str) -> None:
        self._partes.append(data)
        if self._en_h2:
            self._h2_parte.append(data)

    @property
    def texto_plano(self) -> str:
        return _normalizar_espacios(" ".join(self._partes))

    @property
    def palabras(self) -> int:
        return len(self.texto_plano.split()) if self.texto_plano else 0


def _normalizar_espacios(valor: str) -> str:
    return re.sub(r"\s+", " ", valor).strip()


def _analizar(cuerpo_html: str) -> _AnalizadorHTML:
    parser = _AnalizadorHTML()
    parser.feed(cuerpo_html)
    parser.close()
    if parser.error:
        raise PedidoMalo(parser.error)
    return parser


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def _es_propio(url: str, dominio: str) -> bool:
    host = _host(url)
    return host == dominio or host.endswith("." + dominio)


def _url_permitida(
    url: str, fuentes: set[str], enlaces_internos: set[str], dominio: str, oficiales: dict
) -> bool:
    if not es_url(url):
        raise PedidoMalo(f"la URL {url!r} no es válida")
    if url in fuentes or url in enlaces_internos or url in oficiales:
        return True
    if _es_propio(url, dominio):
        return True
    raise PedidoMalo(
        f"la URL {url} no es de {dominio} ni viene en fuentes, enlaces_internos o la lista de "
        "fuentes oficiales"
    )


def _fuentes_citadas(
    hrefs: list[str], fuentes: set[str], dominio: str, oficiales: dict
) -> list[str]:
    """Fuentes externas distintas que cita el cuerpo, en orden de aparición."""
    citadas: list[str] = []
    for url in hrefs:
        if url in citadas or _es_propio(url, dominio):
            continue
        if url in oficiales or url in fuentes:
            citadas.append(url)
    return citadas


def fecha_larga(dia: date) -> str:
    return f"{dia.day} de {MESES[dia.month - 1]} de {dia.year}"


def _hoy() -> date:
    return datetime.now(ZoneInfo("America/Mexico_City")).date()


def _cierre(cfg: dict, citadas: list[str], revisor: str, actualizado: date) -> str:
    """Lista de fuentes y firma que el código pone al final del artículo (antes del disclaimer)."""
    items = "".join(
        f'<li><a href="{html.escape(url)}">'
        f"{html.escape(cfg['fuentes'].get(url) or _host(url))}</a></li>"
        for url in citadas
    )
    firma = f"Escrito por el equipo editorial de {cfg['nombre']}"
    if revisor:
        firma += f"; revisado por {html.escape(revisor)}"
    firma += f". Actualizado el {fecha_larga(actualizado)}."
    return f"<p><strong>Fuentes consultadas</strong></p><ul>{items}</ul><p><em>{firma}</em></p>"


def _avisos_calidad(
    analisis: _AnalizadorHTML, faq: list[dict], revisor: str, hrefs: list[str], dominio: str
) -> list[str]:
    """Avisos para el aprobador: no bloquean, señalan lo que le falta para ser un buen artículo."""
    avisos: list[str] = []
    if not revisor:
        avisos.append(
            "sin revisor con nombre: agrega «- revisor: Nombre, puesto» en «Datos verificados» "
            "de la ficha"
        )
    practico = {"table", "ol"} & analisis.etiquetas or "ejemplo" in _plegar_ascii(
        analisis.texto_plano
    )
    if not practico:
        avisos.append("sin tabla, pasos numerados ni ejemplo: revisa que aporte algo práctico")
    if len(faq) < MIN_FAQ:
        avisos.append(f"solo {len(faq)} preguntas frecuentes; lo ideal son {MIN_FAQ} o más")
    if not any(_es_propio(url, dominio) for url in hrefs):
        avisos.append(f"sin enlaces internos a {dominio}")
    return avisos


def _con_disclaimer(cuerpo_html: str, analisis: _AnalizadorHTML, disclaimer: str) -> str:
    """Agrega al final el disclaimer de la ficha si el cuerpo no lo trae textual."""
    if _normalizar_espacios(disclaimer) in analisis.texto_plano:
        return cuerpo_html
    return f"{cuerpo_html}<p>{html.escape(disclaimer, quote=False)}</p>"


def _cumplimiento(
    titulo: str,
    meta: str,
    cuerpo: _AnalizadorHTML,
    faq: list[dict],
    marca: str,
    datos: dict | None = None,
) -> None:
    renglones = [titulo, meta, cuerpo.texto_plano]
    renglones += [f"{item['pregunta']} {item['respuesta']}" for item in faq]
    resultado = revisar(marca, "\n".join(renglones), "articulo", datos=datos)
    if not resultado["ok"]:
        detalle = "; ".join(f"{b['regla']}: {b['detalle']}" for b in resultado["bloqueos"])
        raise PedidoMalo(detalle)


def leer_articulo(
    contenido: str,
    keyword: str,
    fuentes: set[str] | None = None,
    enlaces_internos: set[str] | None = None,
    marca: str = "",
    datos: dict | None = None,
    revisor: str = "",
    hoy: date | None = None,
) -> dict:
    """Valida el JSON de GPT y devuelve el artículo listo para revisión humana (sin publicar).

    `datos`: los «Datos verificados» de la ficha (fijan el disclaimer si la marca lo exige).
    `revisor`: nombre de quien revisa (vacío = la firma no lo menciona y se avisa).
    """
    fuentes = fuentes or set()
    enlaces_internos = enlaces_internos or set()
    cfg = blog_de(marca)
    dominio = cfg["dominio"]
    datos = datos or {}
    if not isinstance(contenido, str):
        raise PedidoMalo("GPT no devolvió texto")
    try:
        rep = json.loads(contenido)
    except json.JSONDecodeError:
        raise PedidoMalo("GPT no devolvió JSON válido") from None
    if not isinstance(rep, dict):
        raise PedidoMalo("GPT no devolvió un objeto JSON")

    titulo = texto(rep.get("titulo"), "titulo")
    if len(titulo) > MAX_TITULO:
        raise PedidoMalo(f"el título tiene {len(titulo)} caracteres; el máximo es {MAX_TITULO}")
    slug = normalizar_slug(titulo)

    meta = texto(rep.get("meta_descripcion"), "meta_descripcion")
    if len(meta) > MAX_META:
        raise PedidoMalo(
            f"la meta descripción tiene {len(meta)} caracteres; el máximo es {MAX_META}"
        )

    brief_raw = rep.get("brief")
    if not isinstance(brief_raw, dict):
        raise PedidoMalo("«brief» debe ser un objeto")
    intencion = brief_raw.get("intencion")
    if intencion not in INTENCIONES:
        raise PedidoMalo(
            f"«brief.intencion» debe ser una de {', '.join(INTENCIONES)}: {intencion!r}"
        )
    brief = {
        "intencion": intencion,
        "h2s": _lista_texto(brief_raw.get("h2s"), "brief.h2s", requerida=True),
        "preguntas": _lista_texto(brief_raw.get("preguntas"), "brief.preguntas", requerida=True),
    }

    cuerpo_html = texto(rep.get("cuerpo_html"), "cuerpo_html")
    analisis = _analizar(cuerpo_html)
    if not MIN_PALABRAS <= analisis.palabras <= MAX_PALABRAS:
        raise PedidoMalo(
            f"el cuerpo tiene {analisis.palabras} palabras; debe tener entre "
            f"{MIN_PALABRAS} y {MAX_PALABRAS}"
        )
    if not MIN_H2 <= len(analisis.h2s) <= MAX_H2:
        raise PedidoMalo(
            f"el cuerpo tiene {len(analisis.h2s)} h2; debe tener entre {MIN_H2} y {MAX_H2}"
        )
    primer_h2 = analisis.h2s[0] if analisis.h2s else ""
    if not (_contiene(keyword, titulo) or _contiene(keyword, primer_h2)):
        raise PedidoMalo("la keyword no aparece en el título ni en el primer h2")

    for url in analisis.hrefs:
        _url_permitida(url, fuentes, enlaces_internos, dominio, cfg["fuentes"])
    citadas = _fuentes_citadas(analisis.hrefs, fuentes, dominio, cfg["fuentes"])
    if len(citadas) < MIN_FUENTES:
        raise PedidoMalo(
            f"el cuerpo cita {len(citadas)} fuentes; debe citar al menos {MIN_FUENTES} distintas "
            "con <a href>, de «fuentes» del pedido o de la lista de fuentes oficiales"
        )

    valor_unico = texto(rep.get("valor_unico"), "valor_unico")

    faq = []
    for item in _lista_objetos(rep.get("faq"), "faq"):
        pregunta = texto(item.get("pregunta"), "pregunta")
        respuesta = texto(item.get("respuesta"), "respuesta")
        faq.append({"pregunta": pregunta, "respuesta": respuesta})

    avisos = _avisos_calidad(analisis, faq, revisor, analisis.hrefs, dominio)
    actualizado = hoy or _hoy()
    cuerpo_html += _cierre(cfg, citadas, revisor, actualizado)
    analisis = _analizar(cuerpo_html)
    if cfg["disclaimer_obligatorio"] and datos.get("disclaimer"):
        cuerpo_html = _con_disclaimer(cuerpo_html, analisis, datos["disclaimer"])
        analisis = _analizar(cuerpo_html)
    _cumplimiento(titulo, meta, analisis, faq, marca, datos)

    return {
        "titulo": titulo,
        "slug": slug,
        "meta_descripcion": meta,
        "brief": brief,
        "cuerpo_html": cuerpo_html,
        "faq": faq,
        "palabras": analisis.palabras,
        "notas": texto(rep.get("notas"), "notas", requerido=False),
        "valor_unico": valor_unico,
        "autor": f"Equipo editorial de {cfg['nombre']}",
        "revisor": revisor,
        "actualizado": actualizado.isoformat(),
        "fuentes_citadas": citadas,
        "calidad": {"fuentes": len(citadas), "avisos": avisos},
    }


def sintetizar(
    ficha: str,
    pedido: dict,
    llave: str,
    modelo: str = "gpt-5.5",
    enviar: Callable[[dict, str], dict] = _enviar_urllib,
    intentos: int = 2,
    hoy: date | None = None,
) -> dict:
    """Pide el artículo a GPT; si no cumple las reglas, le devuelve el error y reintenta una vez."""
    if not llave:
        raise RuntimeError("falta OPENAI_API_KEY en el secret de Modal")
    datos = _datos_pedido(pedido)
    verificados = datos_de_marca(datos["marca"], ficha)  # sin datos exigidos no se gasta en GPT
    revisor = revisor_de(ficha, pedido)
    mensajes = armar_mensajes(ficha, pedido)
    fuentes = set(datos["fuentes"])
    enlaces_internos = set(datos["enlaces_internos"])
    error = ""
    for _ in range(intentos):
        datos_openai = enviar(
            {"model": modelo, "messages": mensajes, "response_format": {"type": "json_object"}},
            llave,
        )
        try:
            contenido = datos_openai["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            contenido = None  # sin texto: cuenta como respuesta que no cumple y se reintenta
        try:
            articulo = leer_articulo(
                contenido,
                datos["keyword"],
                fuentes=fuentes,
                enlaces_internos=enlaces_internos,
                marca=datos["marca"],
                datos=verificados,
                revisor=revisor,
                hoy=hoy,
            )
        except PedidoMalo as exc:
            error = str(exc)
            mensajes = mensajes + [
                {"role": "assistant", "content": contenido if isinstance(contenido, str) else ""},
                {"role": "user", "content": f"No cumple las reglas: {error}. Corrígelo."},
            ]
            continue
        articulo["modelo"] = modelo
        articulo["uso"] = (
            datos_openai.get("usage") if isinstance(datos_openai, dict) else None
        ) or {}
        return articulo
    raise PedidoMalo(f"GPT no logró un artículo válido: {error}")


def atender(
    pedido: dict,
    token: str | None,
    token_esperado: str | None,
    llave: str,
    modelo: str = "gpt-5.5",
    enviar: Callable[[dict, str], dict] = _enviar_urllib,
) -> dict:
    """Lógica de POST /articulo: token, marca y ficha se revisan antes de gastar en GPT."""
    from app.servicio import token_valido

    if not token_valido(token, token_esperado):
        raise ErrorHTTP(401, "token inválido")
    marca, ficha = ficha_del_pedido(pedido)
    try:
        articulo = sintetizar(ficha, pedido, llave, modelo=modelo, enviar=enviar)
    except PedidoMalo as exc:
        raise ErrorHTTP(422, str(exc)) from None
    except RuntimeError as exc:
        raise ErrorHTTP(502, str(exc)) from None
    return {"marca": marca, **articulo}
