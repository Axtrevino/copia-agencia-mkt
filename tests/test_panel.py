"""Prueba del panel (panel/index.html) en un navegador con datos simulados.

Los webhooks de n8n se interceptan: no hace falta un n8n real. Se salta si Playwright no está
instalado (pip install playwright && playwright install chromium).
"""

from __future__ import annotations

import json
import random
from contextlib import nullcontext
from datetime import date, timedelta
from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

PANEL = Path(__file__).resolve().parent.parent / "panel" / "index.html"
SALIDA = Path(__file__).resolve().parent / "capturas"
MARCAS = ("marca-a", "marca-b")


def _dias(n: int, hasta: date) -> list[str]:
    return [(hasta - timedelta(days=n - 1 - i)).isoformat() for i in range(n)]


def datos_panel(hoy: date) -> dict:
    """Respuesta simulada de «Panel (lectura)» (flujo 60)."""
    posts = []
    for i in range(6):
        posts.append(
            {
                "post_id": f"MA-FB-2026-{i:04d}",
                "marca": MARCAS[i % 2],
                "fecha": (hoy + timedelta(days=i - 2)).isoformat(),
                "hora": "10:00",
                "estado": [
                    "publicado",
                    "publicado",
                    "por aprobar",
                    "planeado",
                    "aprobado",
                    "por aprobar",
                ][i],
                "version": 1,
                "titular": f"Titular de prueba {i}",
                "copy": "Texto de prueba.",
                "tema": "Tema",
            }
        )
    return {
        "generado": f"{hoy.isoformat()} 10:13",
        "dias": 28,
        "kpis": {"leads": 9, "publicados": 2, "por_aprobar": 2, "articulos_por_aprobar": 1},
        "leads": {
            "por_marca": {"marca-a": 6, "marca-b": 3},
            "por_fuente": {"Meta": 4, "google": 5},
            "por_dia": {},
            "ultimos": [
                {
                    "fecha": f"{hoy.isoformat()} 09:00",
                    "marca": "marca-a",
                    "origen": "sitio",
                    "estado": "nuevo",
                    "empresa": "Empresa X",
                    "utm_source": "google",
                }
            ],
        },
        "posts": posts,
        "articulos": [
            {
                "id": 1,
                "marca": "marca-a",
                "keyword": "palabra clave",
                "titulo": "Artículo de prueba",
                "estado": "por aprobar",
                "volumen": 320,
            }
        ],
        "hallazgos": [],
        "campanas": [],
        "decisiones": [],
    }


def datos_analytics(hoy: date, sin_anterior_b: bool = True) -> dict:
    """Respuesta simulada de «Panel analytics (lectura)» (flujo 62)."""
    rnd = random.Random(7)
    hasta = hoy - timedelta(days=1)
    dias = _dias(28, hasta)
    ant = _dias(28, hasta - timedelta(days=28))
    out = {
        "generado": f"{hoy.isoformat()} 10:13",
        "dias": 28,
        "desde": dias[0],
        "hasta": dias[-1],
        "ant_desde": ant[0],
        "ant_hasta": ant[-1],
        "sheet_url": "https://docs.google.com/spreadsheets/d/ejemplo/edit",
        "marcas": {},
    }
    for k, m in enumerate(MARCAS):
        f = 1 if k == 0 else 0.35
        diario = {
            d: {"s": int(rnd.randint(5, 30) * f), "e": int(rnd.randint(2, 12) * f)} for d in dias
        }
        diario_ant = (
            {}
            if (k == 1 and sin_anterior_b)
            else {d: {"s": int(rnd.randint(4, 22) * f), "e": 3} for d in ant}
        )
        ses = sum(v["s"] for v in diario.values())
        out["marcas"][m] = {
            "nombre": "Marca A" if k == 0 else "Marca B",
            "dominio": f"{m}.com",
            "lead": {"nombre": "generate_lead", "etiqueta": "Dejaron sus datos"},
            "medio": {"nombre": "form_start", "etiqueta": "Empezaron el formulario"},
            "ga4_url": "https://analytics.google.com/",
            "gsc_url": "https://search.google.com/search-console",
            "ga4": {
                "error": "",
                "sesiones": ses,
                "sesiones_ant": sum(v["s"] for v in diario_ant.values()),
                "enganchadas": sum(v["e"] for v in diario.values()),
                "enganchadas_ant": 3 * len(diario_ant),
                "usuarios": int(ses * 0.7),
                "diario": diario,
                "diario_ant": diario_ant,
                "canales": [
                    {
                        "canal": "Organic Search",
                        "s": int(ses * 0.5),
                        "s_ant": int(ses * 0.4),
                        "e": int(ses * 0.3),
                    },
                    {
                        "canal": "Direct",
                        "s": int(ses * 0.3),
                        "s_ant": int(ses * 0.35),
                        "e": int(ses * 0.1),
                    },
                    {"canal": "Paid Search", "s": int(ses * 0.1), "s_ant": 0, "e": 0},
                    {"canal": "Organic Social", "s": int(ses * 0.05), "s_ant": 2, "e": 1},
                    {"canal": "Referral", "s": 6, "s_ant": 3, "e": 2},
                    {"canal": "Unassigned", "s": 3, "s_ant": 1, "e": 0},
                ],
                "paginas": [
                    {"pagina": p, "s": int(ses * w)}
                    for p, w in (
                        ("/", 0.55),
                        ("/contacto", 0.1),
                        ("/servicios", 0.08),
                        ("/blog/guia", 0.05),
                        ("/precios", 0.04),
                        ("/nosotros", 0.02),
                    )
                ],
                "eventos": {
                    "page_view": [ses * 2, ses],
                    "generate_lead": [12 - 9 * k, 9],
                    "form_start": [31 - 20 * k, 20],
                    "contacto_click": [6, 4],
                    "form_submit": [11, 7],
                },
                "atribucion": [
                    {"primero": "Organic Search", "ultimo": "Organic Search", "n": 7 - 5 * k},
                    {"primero": "Direct", "ultimo": "Direct", "n": 3},
                    {"primero": "Direct", "ultimo": "Organic Search", "n": 2},
                ],
            },
            "gsc": {
                "error": "",
                "clics": 80 - 50 * k,
                "impresiones": 2100 - 1500 * k,
                "posicion": 7.1 + 7 * k,
                "clics_ant": 0,
                "impresiones_ant": 0,
                "diario": {
                    d: {"c": rnd.randint(0, 6), "i": int(rnd.randint(30, 120) * f)}
                    for d in dias[6:]
                },
                "consultas": [
                    {"q": f"búsqueda {i}", "c": 10 - i, "i": 300 - 40 * i, "pos": 4 + i}
                    for i in range(5)
                ],
                "paginas": [],
            },
            "meta": {"anuncios": {}, "pagina": {d: rnd.choice([0, 0, 0, 25, 30]) for d in dias}},
            "leads_sheet": {"total": 6 - 3 * k, "clientes": 0, "medido": False},
        }
    out["seo"] = {
        "fecha_pos": hoy.isoformat(),
        "posiciones": [
            {
                "marca": "marca-a",
                "keyword": "servicio principal",
                "volumen": 1900,
                "posicion": 6,
                "anterior": 9,
                "cambio": "▲3",
                "url": "",
            },
            {
                "marca": "marca-a",
                "keyword": "servicio en la ciudad",
                "volumen": 1300,
                "posicion": 9,
                "anterior": 9,
                "cambio": "=",
                "url": "",
            },
            {
                "marca": "marca-b",
                "keyword": "producto b",
                "volumen": 2400,
                "posicion": 18,
                "anterior": 14,
                "cambio": "▼4",
                "url": "",
            },
            {
                "marca": "marca-a",
                "keyword": "servicio barato",
                "volumen": 140,
                "posicion": None,
                "anterior": None,
                "cambio": "sigue fuera",
                "url": "",
            },
        ],
        "fecha_onpage": hoy.isoformat(),
        "paginas": [
            {
                "marca": "marca-a",
                "url": "https://marca-a.com/nosotros",
                "prioridad": "alta",
                "problemas": "Sin H1; Título repetido en otra página; Carga lenta (4.2 s)",
            },
            {
                "marca": "marca-b",
                "url": "https://marca-b.com/preguntas",
                "prioridad": "alta",
                "problemas": "Poco texto (180 palabras)",
            },
            {
                "marca": "marca-a",
                "url": "https://marca-a.com/blog",
                "prioridad": "media",
                "problemas": "Imágenes sin texto alternativo; Descripción larga (190 caracteres)",
            },
        ],
        "propuestas": [
            {
                "fila": 2,
                "fecha": hoy.isoformat(),
                "marca": "marca-a",
                "url": "https://marca-a.com/servicios",
                "cambio": "titulo",
                "actual": "Servicios | Marca A",
                "propuesta": "Servicio principal en tu ciudad: precios y tiempos | Marca A",
                "por_que": "320 impresiones y 0 clics en 28 días.",
            },
            {
                "fila": 3,
                "fecha": hoy.isoformat(),
                "marca": "marca-b",
                "url": "https://marca-b.com/contacto",
                "cambio": "descripcion",
                "actual": "",
                "propuesta": "Déjanos tus datos y te contamos cómo funciona, sin compromiso.",
                "por_que": "Es la página de leads; Google arma un texto al azar.",
            },
        ],
    }
    return out


def datos_agentes(hoy: date) -> dict:
    nombres = [
        "Agencia · Research semanal",
        "Agencia · Analista semanal",
        "Agencia · Ideas semanales",
        "Agencia · Preparar posts (Marca A)",
        "Agencia · Preparar posts (Marca B)",
        "Agencia · Telegram (respuestas)",
        "Agencia · Publicar posts (Marca A)",
        "Agencia · Publicar posts (Marca B)",
        "Agencia · BigQuery diario",
        "Agencia · Leads a BigQuery",
        "Agencia · Meta Ads optimizador",
        "Agencia · SEO posiciones y on-page",
        "Agencia · SEO (borradores)",
        "Agencia · SEO acciones",
        "Agencia · Leads",
        "Agencia · Vigilante",
        "Agencia · Panel (lectura)",
        "Agencia · Leads (preparar hoja, manual)",
        "Agencia · BigQuery preparar (manual)",
    ]
    flujos = [
        {
            "id": f"w{i}",
            "nombre": n,
            "activo": n not in ("Agencia · Analista semanal",) and "manual" not in n,
            "actualizado": "",
        }
        for i, n in enumerate(nombres)
    ]
    inicio = f"{hoy.isoformat()}T16:07:00.000Z"
    corridas = [
        {"flujo": "w3", "estado": "success", "modo": "trigger", "inicio": inicio, "fin": inicio},
        {"flujo": "w8", "estado": "error", "modo": "trigger", "inicio": inicio, "fin": inicio},
    ]
    encargos = [
        {
            "numero": 12,
            "titulo": "Reporte mensual de Paid",
            "estado": "open",
            "etiquetas": ["encargo", "espera-ok"],
            "url": "https://github.com/x/y/issues/12",
            "actualizado": "",
        },
        {
            "numero": 11,
            "titulo": "Cambiar la hora de Preparar Marca B",
            "estado": "open",
            "etiquetas": ["encargo", "en-curso"],
            "url": "https://github.com/x/y/issues/11",
            "actualizado": "",
        },
        {
            "numero": 9,
            "titulo": "Prender métricas",
            "estado": "closed",
            "etiquetas": ["encargo"],
            "url": "https://github.com/x/y/issues/9",
            "actualizado": "",
        },
    ]
    return {
        "generado": f"{hoy.isoformat()} 10:13",
        "error_n8n": "",
        "flujos": flujos,
        "corridas": corridas,
        "error_github": "",
        "encargos": encargos,
    }


@pytest.fixture(scope="module")
def navegador():
    with sync_api.sync_playwright() as p:
        nav = p.chromium.launch()
        yield nav
        nav.close()


@pytest.fixture(scope="module")
def pagina(navegador):
    hoy = date.today()
    respuestas = {
        "agencia-panel?": datos_panel(hoy),
        "agencia-panel-analytics": datos_analytics(hoy),
        "agencia-panel-agentes": datos_agentes(hoy),
    }
    pedidos: list[tuple[str, str]] = []

    def responder(route, request):
        url = request.url
        pedidos.append((url, request.post_data or ""))
        if "agencia-panel-seo" in url:
            return route.fulfill(
                json={
                    "ok": True,
                    "mensaje": "1 propuesta aprobada.",
                }
            )
        for clave, cuerpo in respuestas.items():
            if clave in url:
                return route.fulfill(json=cuerpo)
        return route.fulfill(status=404, body="{}")

    with nullcontext():
        ctx = navegador.new_context(viewport={"width": 1440, "height": 900})
        ctx.add_init_script(
            "localStorage.setItem('panel_url','https://n8n.ejemplo.com');localStorage.setItem('panel_token','t');localStorage.setItem('panel_nombre','Agencia')"
        )
        ctx.route("https://n8n.ejemplo.com/**", responder)
        ctx.route("https://fonts.googleapis.com/**", lambda r, q: r.abort())
        pg = ctx.new_page()
        errores: list[str] = []
        pg.on("pageerror", lambda e: errores.append(str(e)))
        pg.goto(PANEL.as_uri())
        pg.wait_for_selector("#badgeHoy:not([hidden])")
        pg.errores = errores
        pg.pedidos = pedidos
        yield pg
        ctx.close()


def _tab(pg, nombre):
    pg.click(f'nav button[data-tab="{nombre}"]')
    pg.wait_for_timeout(100)


def _captura(pg, nombre):
    SALIDA.mkdir(exist_ok=True)
    pg.screenshot(path=str(SALIDA / f"{nombre}.png"), full_page=True)


def test_menu_igual_al_diseno(pagina):
    tabs = pagina.locator("nav button").all_inner_texts()
    assert [t.split("\n")[0].strip() for t in tabs][:7] == [
        "Hoy",
        "Resultados",
        "Analytics",
        "Paid",
        "Contenido",
        "SEO",
        "Agentes",
    ]


def test_resultados(pagina):
    _tab(pagina, "resultados")
    txt = pagina.inner_text("#contenido")
    assert "Embudo" in txt and "Quién se lleva el mérito" in txt
    assert pagina.locator(".embudo:not(.compacto) .etapa").count() == 5
    assert "Aquí se pierde más" in txt
    assert pagina.locator(".apilados .mini").count() == 2
    assert "caminos" in txt.lower() and "lectura" in txt.lower()
    _captura(pagina, "resultados")
    assert not pagina.errores


def test_analytics_y_detalle(pagina):
    _tab(pagina, "analytics")
    txt = pagina.inner_text("#contenido")
    for t in (
        "Visitas por día",
        "De dónde llegan",
        "Por dónde entran",
        "Lo que hicieron",
        "Clics desde Google",
        "Interacción",
    ):
        assert t in txt
    assert pagina.locator("svg.graf rect").count() > 20
    _captura(pagina, "analytics")
    pagina.click(".heroe-a .n1.tocable")
    pagina.wait_for_selector("#detalle:not([hidden])")
    dt = pagina.inner_text("#detalle")
    assert "Día por día" in dt and "cómo se mide" in dt.lower() and "Mejor día" in dt
    assert pagina.locator("#detalle polyline.gp").count() == 1
    pagina.click('#detalle [data-ver="dias"]')
    assert pagina.locator("#detalle table.tabla-d tr").count() == 29
    _captura(pagina, "detalle-visitas")
    pagina.keyboard.press("Escape")
    pagina.wait_for_selector("#detalle", state="hidden")
    assert not pagina.errores


def test_detalle_nos_vieron(pagina):
    _tab(pagina, "resultados")
    pagina.click('.embudo:not(.compacto) .etapa[data-det="vieron"]')
    pagina.wait_for_selector("#detalle:not([hidden])")
    dt = pagina.inner_text("#detalle")
    assert "Qué buscaban" in dt and "Por fuente y marca" in dt
    _captura(pagina, "detalle-vieron")
    pagina.click("#detalle .btn[data-cerrar-det]")
    pagina.wait_for_selector("#detalle", state="hidden")


def test_seo_aprobar(pagina):
    _tab(pagina, "seo")
    txt = pagina.inner_text("#contenido")
    for t in ("veces nos", "Por aprobar", "Keywords", "Páginas por arreglar", "Artículos del blog"):
        assert t in txt
    assert pagina.locator(".prop-seo").count() == 2
    _captura(pagina, "seo")
    pagina.click('.prop-seo button[data-seo="aprobar"]')
    pagina.wait_for_selector("text=propuesta aprobada")
    cuerpo = [b for u, b in pagina.pedidos if "agencia-panel-seo" in u][-1]
    assert json.loads(cuerpo) == {"accion": "aprobar", "filas": [2]}
    assert pagina.locator(".prop-seo").count() == 1


def test_agentes(pagina):
    _tab(pagina, "agentes")
    txt = pagina.inner_text("#contenido")
    assert "Cómo trabajan, en orden" in txt and "Encargos" in txt and "Detrás del panel" in txt
    assert pagina.locator(".grupo").count() == 6
    assert "Espera tu OK" in txt
    assert pagina.locator(".ag .punto[style*='var(--down)']").count() == 1
    _captura(pagina, "agentes")


def test_filtro_de_marca(pagina):
    _tab(pagina, "resultados")
    pagina.click('#marcas button[data-m="marca-b"]')
    assert pagina.locator(".apilados").count() == 0
    _tab(pagina, "analytics")
    assert "MARCA B" in pagina.inner_text(".heroe-a .ceja-s").upper()
    pagina.click('#marcas button[data-m=""]')
    assert not pagina.errores


def test_sin_flujo_de_analytics(navegador):
    """Si el flujo 62 no está, las pestañas dicen qué falta en vez de romperse."""
    hoy = date.today()
    with nullcontext():
        ctx = navegador.new_context()
        ctx.add_init_script(
            "localStorage.setItem('panel_url','https://n8n.ejemplo.com');localStorage.setItem('panel_token','t')"
        )
        ctx.route(
            "https://n8n.ejemplo.com/**",
            lambda r, q: (
                r.fulfill(json=datos_panel(hoy))
                if "agencia-panel?" in q.url
                else r.fulfill(status=404, body="{}")
            ),
        )
        ctx.route("https://fonts.googleapis.com/**", lambda r, q: r.abort())
        pg = ctx.new_page()
        errores: list[str] = []
        pg.on("pageerror", lambda e: errores.append(str(e)))
        pg.goto(PANEL.as_uri())
        pg.wait_for_selector("#badgeHoy:not([hidden])")
        for t in ("resultados", "analytics", "seo", "agentes"):
            pg.click(f'nav button[data-tab="{t}"]')
        assert "sin conectar" in pg.inner_text("#contenido")
        pg.click('nav button[data-tab="analytics"]')
        assert "Conecta GA4 y Search Console" in pg.inner_text("#contenido")
        ctx.close()
        assert not errores
