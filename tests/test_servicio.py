"""Pruebas del servicio con la marca de ejemplo (`marcas/marca-a/`). Sin red."""

from __future__ import annotations

import base64
import io
import json
from datetime import date

import pytest
from PIL import Image

from app import marcas
from app.articulo import leer_articulo, normalizar_slug
from app.ideas import leer_ideas, temporada_de
from app.imagen import Imagen
from app.pieza import PedidoMalo, Textos, armar_prompt, sistemas_de, validar
from app.redactor import armar_mensajes, leer_idea, liga_utm, redactar
from app.reglas import revisar
from app.servicio import atender, token_valido

M = "marca-a"


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (1088, 1360), "white").save(buf, "PNG")
    return buf.getvalue()


def test_config_de_ejemplo():
    cfg = marcas.config(M)
    assert cfg["nombre"] == "Marca A"
    assert set(sistemas_de(M)) == {"foto_titular_abajo", "panel_lateral", "tarjeta_clara"}


def test_marca_invalida():
    with pytest.raises(marcas.MarcaDesconocida):
        marcas.config("../etc")
    with pytest.raises(marcas.MarcaDesconocida):
        marcas.config("no-existe")


def test_prompt_lleva_reglas_y_textos():
    t = Textos(titular="Tu tienda abre los domingos", palabra_acento="domingos")
    prompt = armar_prompt("panel_lateral", t, "Una tienda de barrio en la mañana", M)
    assert "Marca A" in prompt
    assert '"Tu tienda abre los domingos"' in prompt
    assert "#F28C28" in prompt
    assert "WHITE logo" in prompt


def test_validar_limites():
    with pytest.raises(PedidoMalo):
        validar("panel_lateral", Textos(titular="x" * 61), M)
    with pytest.raises(PedidoMalo):
        validar("no_existe", Textos(titular="Hola"), M)


def test_token():
    assert token_valido("abc", "abc")
    assert not token_valido("abc", None)
    assert not token_valido("", "abc")


def test_atender_genera_jpeg():
    pedido = {
        "marca": M,
        "sistema": "foto_titular_abajo",
        "post_id": "EJ-1",
        "escena": "Dos personas en un mercado",
        "textos": {"titular": "Compra local"},
    }
    res = atender(pedido, lambda p, r: Imagen(_png(), "m", 0.1, {}), [])
    assert res["archivo"] == "EJ-1-v1.jpg"
    assert (res["ancho"], res["alto"]) == (1080, 1350)
    assert base64.b64decode(res["pieza_jpeg_b64"])[:2] == b"\xff\xd8"


def test_reglas_palabras_prohibidas():
    assert not revisar(M, "Resultado garantizado")["ok"]
    assert revisar(M, "Resultado real")["ok"]
    assert revisar(M, "lo usas en el día a día")["avisos"]


def test_liga_utm():
    liga = liga_utm(M, "EJ-FB-01")
    assert liga.startswith("https://www.marca-a.com/?utm_source=meta")
    assert liga.endswith("utm_content=ej-fb-01")


def _idea(**extra):
    base = {
        "opciones_titular": ["Abre en domingo", "¿Domingo libre?", "Tres razones"],
        "escena": "Una tienda de barrio",
        "sistema": "panel_lateral",
        "textos": {"titular": "Abre en domingo"},
        "copy": "Ahora abrimos en domingo.\n#ejemplo",
        "notas": "el más claro",
    }
    base.update(extra)
    return json.dumps(base)


def test_leer_idea_agrega_liga():
    pedido = {"marca": M, "post_id": "EJ-1", "fecha": "2026-12-01"}
    idea = leer_idea(_idea(), M, pedido=pedido)
    assert "Conoce más: https://www.marca-a.com/?" in idea["copy"]
    assert idea["copy"].splitlines()[-1] == "#ejemplo"
    assert idea["alcance"] == "imagen"


def test_leer_idea_no_repite_plantilla():
    pedido = {
        "marca": M,
        "post_id": "EJ-2",
        "fecha": "2026-12-03",
        "recientes": [{"fecha": "2026-12-01", "sistema": "panel_lateral"}],
    }
    with pytest.raises(PedidoMalo):
        leer_idea(_idea(), M, pedido=pedido)


def test_redactar_reintenta_y_cumple():
    respuestas = [_idea(copy="Resultado garantizado"), _idea()]

    def enviar(cuerpo, llave):
        return {"choices": [{"message": {"content": respuestas.pop(0)}}]}

    idea = redactar(marcas.ficha(M), {"marca": M, "post_id": "EJ-3"}, "llave", enviar=enviar)
    assert "garantizado" not in idea["copy"]


def test_mensajes_traen_ficha():
    mensajes = armar_mensajes(marcas.ficha(M), {"marca": M, "post_id": "EJ-1"})
    assert "Ficha de marca: Marca A" in mensajes[0]["content"]


def test_temporada_incluye_propias():
    eventos = temporada_de([{"fecha": "2027-03-10"}], marcas.config(M))
    nombres = {e["nombre"] for e in eventos}
    assert "Temporada alta de la industria (ejemplo)" in nombres


def test_leer_ideas_valida_formato():
    posts = [{"post_id": "P1", "fecha": "2026-12-01", "tipo": "educativo"}]
    tema = "Insight: a | Ángulo: b | Gancho: c | Por qué ahora: d"
    contenido = json.dumps(
        {
            "resumen": "ok",
            "ideas": [{"post_id": "P1", "fuente_tipo": "temporada", "fuente": "", "tema": tema}],
        }
    )
    assert leer_ideas(contenido, posts, set())["ideas"][0]["tema"] == tema


def test_slug():
    assert normalizar_slug("Guía de compras 2027") == "guia-de-compras-2027"


def test_articulo_valida_y_firma():
    parrafo = "<p>" + " ".join(["palabra"] * 300) + "</p>"
    cuerpo = (
        "<h2>Guía de compras locales</h2>"
        + parrafo
        + '<p>Según <a href="https://www.inegi.org.mx/">INEGI</a> y '
        + '<a href="https://www.gob.mx/profeco">PROFECO</a>.</p>'
        + "<h2>Paso a paso</h2><ol><li>uno</li></ol>"
        + parrafo
        + "<h2>Cierre</h2>"
        + parrafo
        + '<p><a href="https://www.marca-a.com/contacto">Contacto</a></p>'
    )
    contenido = json.dumps(
        {
            "titulo": "Guía de compras locales",
            "slug": "x",
            "meta_descripcion": "Cómo comprar local.",
            "brief": {"intencion": "informativa", "h2s": ["a"], "preguntas": ["b"]},
            "cuerpo_html": cuerpo,
            "faq": [{"pregunta": f"p{i}", "respuesta": "r"} for i in range(3)],
            "valor_unico": "lista paso a paso",
        }
    )
    art = leer_articulo(contenido, "compras locales", marca=M, hoy=date(2026, 12, 1))
    assert art["slug"] == "guia-de-compras-locales"
    assert "Escrito por el equipo editorial de Marca A" in art["cuerpo_html"]
    assert "1 de diciembre de 2026" in art["cuerpo_html"]
