"""El redactor del agente de contenido: GPT escribe la idea completa de cada post.

Con la ficha de la marca como reglas, GPT propone (o corrige, si hay cambios pedidos) la escena de
la foto, la plantilla, los textos de la imagen y el copy del post. Luego el servicio «pieza»
dibuja exactamente eso. Solo librería estándar; la llamada a OpenAI llega inyectada.

Reglas que no dependen de GPT (salen de `marca.json` y se aplican al leer su respuesta):
- `disclaimer_obligatorio`: el disclaimer de la imagen y del copy es el de «Datos verificados».
- `imagen.solo_titular`: en la imagen va solo el titular; kicker, subtítulo, CTA y URL solo en los
  tipos de `imagen.tipos_con_extras`.
- `copy.max_lineas` / `copy.max_largo_linea`: copy corto (la línea de la liga no cuenta).
- `liga`: el copy lleva siempre la liga del sitio con UTM (`utm_content` = post_id en minúsculas)
  en su propia línea «<CTA>: <liga>». La agrega o corrige el código.
- La plantilla no se repite con la del post anterior, y en posts nuevos GPT propone 3 titulares
  y elige uno.
- Cambios: GPT dice el «alcance». "copy" → escena, plantilla y textos idénticos (la imagen no se
  toca); "textos" → escena y plantilla idénticas (la imagen se edita con `/editar`); "imagen" → se
  rehace. Si falta o no es válido, "imagen". Los posts nuevos siempre son "imagen".
- `ajustes.md` de la marca va después de la ficha y manda sobre ella, salvo «Datos verificados»,
  el disclaimer y las reglas, que el código sigue aplicando.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import asdict
from urllib.parse import urlparse

from app import marcas
from app.datos import MAX_AJUSTES, datos_verificados
from app.pieza import PedidoMalo, Textos, limites_de, sistemas_de, sistemas_para_proponer, validar
from app.reglas import revisar

URL = "https://api.openai.com/v1/chat/completions"
EXTRAS_IMAGEN = ("kicker", "subtitulo", "cta", "url")
_URL = re.compile(r"(?:https?://|www\.)\S+", re.I)
MAX_CTA_LIGA = 40

ENCABEZADO_AJUSTES = """# Ajustes del dueño de la marca

Ajustes de tono y reglas para TODOS los posts de la marca. Mandan sobre la ficha, EXCEPTO en
«Datos verificados», el disclaimer y las reglas legales: esas no cambian con ningún ajuste."""

INSTRUCCIONES = """Eres el redactor de contenido de la marca descrita en la ficha. Respetas la ficha
al pie de la letra: voz, palabras sí y no, datos verificados, hashtags y CTAs permitidos.

Devuelves SOLO un objeto JSON con estas llaves:
- "opciones_titular": 3 titulares distintos para la idea (mecanismos distintos: contraste,
  pregunta, lista, observación). Elige como "textos.titular" el MÁS CLARO de los 3 (que además
  enganche), con las reglas de «Titulares claros» de abajo.
- "escena": qué se ve, en español, concreta y coherente con el copy (personas, lugar, luz, ropa
  con colores distintos, nadie mira a cámara, espacio negativo donde va el texto).
- "sistema": la plantilla, una de {sistemas}.{rotacion}
- "textos": {{"kicker", "titular", "palabra_acento", "subtitulo", "cta", "url", "disclaimer"}}.
  Límites: {limites}. "palabra_acento" es la última palabra del titular (tal cual) o "". Deja ""
  lo que no aplique.{reglas_textos}
- "copy": el texto del post para Facebook e Instagram (máximo {max_copy} caracteres), con
  hashtags al final según la ficha.{reglas_copy}
- "notas": una línea para el aprobador: por qué ese titular es el más claro de los 3 (o qué
  cambiaste y por qué).
- "alcance" (solo cuando corriges una versión con "Cambios pedidos"): qué tanto cambia la pieza.
  - "copy": solo cambia el texto del post; la imagen no se toca. Devuelve "escena", "sistema" y
    "textos" idénticos a la versión actual.
  - "textos": solo cambian palabras impresas en la imagen; la foto y el diseño se quedan.
    Devuelve "escena" y "sistema" idénticos a la versión actual.
  - "imagen": hay que rehacer la imagen (escena, composición, foto, colores, plantilla…).
  Si solo pide cambiar el titular u otro texto de la imagen → "textos"; si solo pide cambiar el
  copy → "copy"; "imagen" solo si pide algo visual o si el texto nuevo no cabe en el diseño.

Titulares claros (también cuando corriges un titular):
- El titular se entiende solo, sin leer el copy ni ver la foto.
- Dice de qué trata el post y por qué le importa a quien lo lee.
- Palabras de todos los días.
- Nada de juegos de palabras, metáforas abstractas, frases a medias ni ganchos crípticos.
- Prueba: alguien que hace scroll entiende el mensaje en 2 segundos.

La imagen, los textos y el copy cuentan la MISMA idea. Si el pedido trae "recientes" (los últimos
posts de la marca), no repitas sus frases, titulares, escenas ni plantillas: otro lugar, otro
encuadre, otro número de personas y otra mecánica (lista, contraste, pregunta, mini historia).

Si el pedido trae "tema", es el brief de la semana (Insight, Ángulo, Gancho, Por qué ahora) que
salió del research de competencia, temporada y público. Construye el post sobre ese insight y ese
ángulo, sin diluirlo en un mensaje genérico; puedes pulir el gancho. La escena debe mostrar esa
tensión concreta, no una escena amable cualquiera.{trilladas}"""

REGLAS_DISCLAIMER_TEXTOS = """
  "disclaimer" va SIEMPRE y es exactamente este texto (no lo cambies):
  "{disclaimer}\""""

REGLAS_DISCLAIMER_COPY = """ Termina el copy (antes de los hashtags) con el disclaimer
  exacto de arriba. Si usas cifras, solo las de «Datos verificados», tal cual, sin redondear."""

REGLAS_SOLO_TITULAR = """
  En la imagen va SOLO el titular. "kicker", "subtitulo", "cta" y "url" se dejan "" salvo que
  el tipo sea {tipos}."""

REGLAS_LINEAS = """ Máximo {n} líneas cortas (una idea por línea, sin párrafos largos)."""

REGLAS_LIGA = """ La liga del sitio con UTM va SIEMPRE en el copy, en una línea aparte
  «<CTA>: <liga>»{no_cuenta}; si falta o viene mal, el sistema la agrega o la corrige."""


def _recientes_ordenados(pedido: dict) -> list[dict]:
    recientes = [r for r in (pedido.get("recientes") or []) if isinstance(r, dict)]
    return sorted(recientes, key=lambda r: str(r.get("fecha") or ""))


def sistema_anterior(pedido: dict) -> str:
    """La plantilla del post anterior (el más reciente con fecha menor a la del pedido)."""
    recientes = _recientes_ordenados(pedido)
    fecha = str(pedido.get("fecha") or "")[:10]
    if fecha:
        recientes = [r for r in recientes if str(r.get("fecha") or "")[:10] < fecha]
    return str(recientes[-1].get("sistema") or "") if recientes else ""


def _disclaimer(cfg: dict, datos: dict) -> str:
    if not cfg["disclaimer_obligatorio"]:
        return ""
    disclaimer = str(datos.get("disclaimer") or "").strip()
    if not disclaimer:
        raise RuntimeError(
            f"la marca {cfg['slug']} exige disclaimer y su ficha no lo trae en «Datos verificados»"
        )
    return disclaimer


def armar_mensajes(ficha: str, pedido: dict, ajustes: str = "") -> list[dict]:
    marca = str(pedido.get("marca") or "")
    cfg = marcas.config(marca)
    sistemas = list(sistemas_para_proponer(marca))
    anterior = sistema_anterior(pedido)
    rotacion = ""
    if anterior and not str(pedido.get("cambios") or "").strip():
        sistemas = [s for s in sistemas if s != anterior] or sistemas
        rotacion = f' No uses "{anterior}": es la plantilla del post anterior.'
    limites = ", ".join(f"{k} {v}" for k, v in limites_de(marca).items()) + " caracteres"
    reglas_textos, reglas_copy = "", ""
    disclaimer = _disclaimer(cfg, datos_verificados(ficha))
    if disclaimer:
        reglas_textos += REGLAS_DISCLAIMER_TEXTOS.format(disclaimer=disclaimer)
        reglas_copy += REGLAS_DISCLAIMER_COPY
    else:
        reglas_textos += '\n  "disclaimer" siempre "".'
    if cfg["imagen"]["solo_titular"]:
        tipos = " o ".join(f'"{t}"' for t in cfg["imagen"]["tipos_con_extras"]) or '"(ninguno)"'
        reglas_textos += REGLAS_SOLO_TITULAR.format(tipos=tipos)
    if cfg["copy"]["max_lineas"]:
        reglas_copy += REGLAS_LINEAS.format(n=cfg["copy"]["max_lineas"])
    if cfg.get("liga", {}).get("sitio"):
        no_cuenta = " que no cuenta en ese límite" if cfg["copy"]["max_lineas"] else ""
        reglas_copy += REGLAS_LIGA.format(no_cuenta=no_cuenta)
    if not cfg["copy"]["emojis"]:
        reglas_copy += " Sin emojis."
    trilladas = ""
    if cfg["frases_trilladas"]:
        trilladas = " Evita lo trillado: " + ", ".join(f'"{f}"' for f in cfg["frases_trilladas"])
        trilladas += "."
    sistema = INSTRUCCIONES.format(
        sistemas=", ".join(sistemas),
        rotacion=rotacion,
        limites=limites,
        reglas_textos=reglas_textos,
        max_copy=cfg["copy"]["max_caracteres"],
        reglas_copy=reglas_copy,
        trilladas=trilladas,
    )
    claves = ("post_id", "fecha", "tipo", "tema", "sistema", "escena", "textos", "copy")
    base = {k: pedido.get(k) for k in claves if pedido.get(k) not in (None, "")}
    if pedido.get("recientes"):
        base["recientes"] = pedido["recientes"]
    cambios = str(pedido.get("cambios") or "").strip()
    if cambios:
        tarea = (
            "Corrige esta versión del post aplicando EXACTAMENTE los cambios pedidos por el "
            'aprobador. Conserva todo lo que no pidió cambiar. Indica en "alcance" qué tanto '
            "cambia (copy, textos o imagen).\n\nVersión actual:\n"
            f"{json.dumps(base, ensure_ascii=False, indent=2)}\n\nCambios pedidos: {cambios}"
        )
    else:
        tarea = (
            "Propón un post nuevo con estos datos del calendario:\n"
            f"{json.dumps(base, ensure_ascii=False, indent=2)}"
        )
    contenido = f"{sistema}\n\n# Ficha de la marca\n\n{ficha}"
    ajustes = (ajustes or "").strip()[:MAX_AJUSTES]
    if ajustes:
        contenido += f"\n\n{ENCABEZADO_AJUSTES}\n\n{ajustes}"
    return [
        {"role": "system", "content": contenido},
        {"role": "user", "content": tarea},
    ]


def liga_utm(marca: str, post_id: str) -> str:
    """Liga del sitio de la marca con UTM; utm_content es el post_id en minúsculas."""
    liga = marcas.config(marca).get("liga") or {}
    if not liga.get("sitio") or not str(post_id or "").strip():
        return ""
    sep = "&" if "?" in liga["sitio"] else "?"
    utm = str(liga.get("utm") or "utm_source=meta&utm_medium=organic_social")
    return f"{liga['sitio']}{sep}{utm}&utm_content={str(post_id).strip().lower()}"


def _dominio(marca: str) -> str:
    sitio = (marcas.config(marca).get("liga") or {}).get("sitio") or ""
    return urlparse(sitio).netloc.lower().removeprefix("www.")


def _url_limpia(url: str) -> str:
    return url.rstrip(".,;:)]»\"'")


def _es_del_sitio(url: str, dominio: str) -> bool:
    if not dominio:
        return False
    host = _url_limpia(url).split("://", 1)[-1].split("/", 1)[0].split("?", 1)[0].lower()
    host = host.removeprefix("www.")
    return host == dominio or host.endswith("." + dominio)


def _es_hashtags(linea: str) -> bool:
    return bool(re.fullmatch(r"(#\S+\s*)+", linea.strip()))


def _con_liga(copy: str, liga: str, cta: str, dominio: str, antes_de: str = "") -> str:
    """Deja en el copy exactamente una línea «<CTA>: <liga>».

    Quita las ligas del sitio sin UTM o con UTM equivocado (si en su línea solo quedaba un CTA,
    se reutiliza ese texto). Si la liga exacta ya está, no la duplica. La línea nueva va antes de
    `antes_de` (el disclaimer) o, si no, antes de los hashtags finales.
    """
    lineas: list[str] = []
    ya_esta = False
    for ln in copy.splitlines():
        urls = [u for u in _URL.findall(ln) if _es_del_sitio(u, dominio)]
        if not urls:
            lineas.append(ln)
            continue
        resto, conserva = ln, False
        for u in urls:
            if _url_limpia(u) == liga and not ya_esta:
                ya_esta = conserva = True
                continue
            resto = resto.replace(_url_limpia(u), "", 1)
        resto = re.sub(r"\s{2,}", " ", resto).rstrip()
        if conserva:
            lineas.append(resto)
            continue
        texto = resto.strip().rstrip(":→-–— ").strip()
        if not texto:
            continue
        if len(texto) <= MAX_CTA_LIGA:
            cta = texto  # la línea solo era el CTA de una liga mala: se reutiliza
            continue
        lineas.append(resto)
    if ya_esta:
        return "\n".join(lineas).strip()
    nueva = f"{cta}: {liga}"
    i = len(lineas)
    if antes_de:
        for j, ln in enumerate(lineas):
            if antes_de in ln:
                i = j
                break
        else:
            antes_de = ""
    if not antes_de:
        while i > 0 and (not lineas[i - 1].strip() or _es_hashtags(lineas[i - 1])):
            i -= 1
        if i == 0:
            i = len(lineas)
    lineas.insert(i, nueva)
    return "\n".join(lineas).strip()


def _sin_liga(copy: str, dominio: str) -> str:
    """El copy sin las URLs del sitio (las arma el código); el texto del CTA sí se revisa."""
    return _URL.sub(lambda m: "" if _es_del_sitio(m.group(0), dominio) else m.group(0), copy)


def _revisar_lineas(copy: str, cfg: dict, dominio: str) -> None:
    max_lineas = cfg["copy"]["max_lineas"]
    max_largo = cfg["copy"]["max_largo_linea"]
    if not max_lineas and not max_largo:
        return
    lineas = [
        ln.strip()
        for ln in copy.splitlines()
        if ln.strip()
        and not _es_hashtags(ln)
        and not any(_es_del_sitio(u, dominio) for u in _URL.findall(ln))
    ]
    if max_lineas and len(lineas) > max_lineas:
        raise PedidoMalo(
            f"el copy tiene {len(lineas)} líneas; el máximo es {max_lineas} cortas "
            "(la línea de la liga no cuenta)"
        )
    for ln in lineas:
        if max_largo and len(ln) > max_largo:
            raise PedidoMalo(
                f"hay una línea de {len(ln)} caracteres; cada línea va de máximo {max_largo}"
            )


def _originales(pedido: dict, marca: str) -> tuple[str, str, Textos] | None:
    """Escena, plantilla y textos de la versión que se corrige, si el pedido los trae completos."""
    escena = str(pedido.get("escena") or "")
    sistema = str(pedido.get("sistema") or "")
    crudos = pedido.get("textos")
    if not escena.strip() or not isinstance(crudos, dict):
        return None
    try:
        if sistema not in sistemas_de(marca):
            return None
    except PedidoMalo:
        return None
    textos = Textos(**{k: str(crudos.get(k) or "") for k in Textos.__dataclass_fields__})
    return escena, sistema, textos


def alcance_de(idea: dict, pedido: dict, marca: str) -> str:
    """El alcance que dijo GPT, si se puede respetar; si no, "imagen" (se rehace la pieza)."""
    if not str(pedido.get("cambios") or "").strip():
        return "imagen"
    alcance = str(idea.get("alcance") or "").strip().lower()
    if alcance not in ("copy", "textos") or _originales(pedido, marca) is None:
        return "imagen"
    return alcance


def _con_disclaimer(copy: str, disclaimer: str) -> str:
    """Pone el disclaimer antes de la línea de hashtags (o al final si no hay)."""
    lineas = copy.rstrip().splitlines()
    if lineas and _es_hashtags(lineas[-1]):
        return "\n".join([*lineas[:-1], disclaimer, lineas[-1]])
    return f"{copy.rstrip()}\n{disclaimer}"


def leer_idea(contenido: str, marca: str, pedido: dict | None = None, datos: dict | None = None):
    """Valida lo que devolvió GPT con las mismas reglas que la pieza y las de la marca."""
    try:
        idea = json.loads(contenido)
    except json.JSONDecodeError:
        raise PedidoMalo("GPT no devolvió JSON válido") from None
    if not isinstance(idea, dict):
        raise PedidoMalo("GPT no devolvió un objeto JSON")
    cfg = marcas.config(marca)
    pedido = pedido or {}
    datos = datos or {}
    nuevo = not str(pedido.get("cambios") or "").strip()
    alcance = alcance_de(idea, pedido, marca)
    originales = _originales(pedido, marca) if alcance != "imagen" else None
    sistema = str(idea.get("sistema") or "")
    crudos = idea.get("textos") or {}
    textos = Textos(**{k: str(crudos.get(k) or "") for k in Textos.__dataclass_fields__})
    if originales:
        sistema = originales[1]
        if alcance == "copy":
            textos = Textos(**asdict(originales[2]))
    cta_copy = textos.cta.strip()

    if cfg["imagen"]["solo_titular"]:
        if str(pedido.get("tipo") or "") not in cfg["imagen"]["tipos_con_extras"]:
            for campo in EXTRAS_IMAGEN:
                setattr(textos, campo, "")
    disclaimer = _disclaimer(cfg, datos) if cfg["disclaimer_obligatorio"] else ""
    textos.disclaimer = disclaimer

    if originales:
        iguales = asdict(textos) == asdict(originales[2])
        if alcance == "copy" and not iguales:
            alcance = "textos"  # las reglas obligan a cambiar un texto de la imagen
        elif alcance == "textos" and iguales:
            alcance = "copy"  # no cambió ninguna palabra de la imagen
    validar(sistema, textos, marca)
    if pedido and nuevo:
        anterior = sistema_anterior(pedido)
        if anterior and sistema == anterior:
            raise PedidoMalo(f"la plantilla «{sistema}» es la del post anterior; usa otra")
        opciones = idea.get("opciones_titular")
        if not isinstance(opciones, list) or len(opciones) != 3:
            raise PedidoMalo("faltan «opciones_titular»: 3 titulares distintos")
        if textos.titular not in [str(o).strip() for o in opciones]:
            raise PedidoMalo("el titular elegido debe ser una de las 3 «opciones_titular»")

    escena = originales[0] if originales else str(idea.get("escena") or "").strip()
    copy = str(idea.get("copy") or "").strip()
    if not escena:
        raise PedidoMalo("falta la escena")
    if not copy:
        raise PedidoMalo("falta el copy")
    if disclaimer and disclaimer not in copy:
        copy = _con_disclaimer(copy, disclaimer)
    dominio = _dominio(marca)
    liga = liga_utm(marca, str(pedido.get("post_id") or ""))
    if liga:
        cta_marca = (cfg.get("liga") or {}).get("cta") or "Conoce más"
        cta = cta_copy if 0 < len(cta_copy) <= MAX_CTA_LIGA else cta_marca
        copy = _con_liga(copy, liga, cta, dominio, antes_de=disclaimer)
    _revisar_lineas(copy, cfg, dominio)
    if len(copy) > cfg["copy"]["max_caracteres"]:
        raise PedidoMalo(
            f"el copy tiene {len(copy)} caracteres con la liga; el máximo es "
            f"{cfg['copy']['max_caracteres']}: acórtalo"
        )
    revision = revisar(
        marca,
        "\n".join([textos.titular, textos.subtitulo, _sin_liga(copy, dominio), disclaimer]),
        "post",
        datos=datos,
    )
    if not revision["ok"]:
        raise PedidoMalo("; ".join(f"{b['regla']}: {b['detalle']}" for b in revision["bloqueos"]))
    salida = {
        "sistema": sistema,
        "escena": escena,
        "textos": asdict(textos),
        "copy": copy,
        "notas": str(idea.get("notas") or "").strip(),
        "alcance": alcance,
        "avisos": revision["avisos"],
    }
    if isinstance(idea.get("opciones_titular"), list):
        salida["opciones_titular"] = [str(o).strip() for o in idea["opciones_titular"]]
    return salida


def _enviar_urllib(cuerpo: dict, llave: str, timeout: int = 180) -> dict:
    req = urllib.request.Request(
        URL,
        data=json.dumps(cuerpo).encode(),
        headers={"Authorization": f"Bearer {llave}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:  # el mensaje de OpenAI no trae la llave
        detalle = exc.read()[:400].decode(errors="replace")
        raise RuntimeError(f"OpenAI respondió {exc.code}: {detalle}") from None


def redactar(
    ficha: str,
    pedido: dict,
    llave: str,
    modelo: str = "gpt-5.5",
    enviar: Callable[[dict, str], dict] = _enviar_urllib,
    intentos: int = 2,
    ajustes: str = "",
) -> dict:
    """Pide la idea a GPT; si no cumple las reglas, le devuelve el error y reintenta una vez."""
    if not llave:
        raise RuntimeError("falta OPENAI_API_KEY en el secret de Modal")
    marca = str(pedido.get("marca") or "")
    datos = datos_verificados(ficha)
    _disclaimer(marcas.config(marca), datos)  # sin disclaimer exigido no se gasta en GPT
    mensajes = armar_mensajes(ficha, pedido, ajustes)
    error = ""
    for _ in range(intentos):
        respuesta = enviar(
            {"model": modelo, "messages": mensajes, "response_format": {"type": "json_object"}},
            llave,
        )
        try:
            contenido = respuesta["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise RuntimeError(f"OpenAI no devolvió texto: {str(respuesta)[:300]}") from None
        try:
            idea = leer_idea(contenido, marca, pedido=pedido, datos=datos)
        except PedidoMalo as exc:
            error = str(exc)
            mensajes = mensajes + [
                {"role": "assistant", "content": contenido},
                {"role": "user", "content": f"No cumple las reglas: {error}. Corrígelo."},
            ]
            continue
        idea["modelo"] = modelo
        idea["uso"] = respuesta.get("usage") or {}
        return idea
    raise PedidoMalo(f"GPT no logró una idea válida: {error}")
