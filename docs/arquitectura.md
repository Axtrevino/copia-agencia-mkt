# Arquitectura

## Piezas

| Pieza | Dónde corre | Para qué |
|---|---|---|
| Servicio `app/` | Modal (se paga por segundo, escala a cero) | Todo lo que necesita un modelo: redactar, hacer imágenes, resumir, escribir artículos. |
| Flujos `n8n/` | Tu n8n (nube o servidor propio) | Horarios, lectura y escritura del Sheet, Telegram, Meta, Webflow, APIs de research. |
| Google Sheet | Google Drive | Calendario de posts, Publicados, Leads, Hallazgos, Keywords. Es la fuente de verdad que edita la persona. |
| Tablas de n8n | Dentro de n8n (Data tables) | `seo_articulos` (calendario del blog) y `paid_campanas` (pedidos de campañas). |
| Telegram | Un grupo con temas | Aprobaciones (✅/✏️), Reportes, Alertas. |
| Panel `panel/` | Cualquier hosting estático o abierto localmente | Ver todo y aprobar sin entrar al Sheet. |

## Servicio (Modal)

Endpoints (todos piden el header `X-Pieza-Token`):

| Ruta | Qué hace |
|---|---|
| `POST /redactar` | Con la ficha de la marca, GPT escribe escena, plantilla, textos de la imagen y copy. En cambios, dice el «alcance»: `copy`, `textos` o `imagen`. |
| `POST /` | GPT Image hace la pieza 4:5 con el logo oficial y la plantilla; sale en JPEG 1080 × 1350. |
| `POST /editar` | Cambia solo los textos impresos de una pieza ya hecha (no rehace la foto). |
| `POST /research` | Resume noticias, anuncios de la competencia y keywords en hallazgos con fuente. |
| `POST /ideas` | Escribe el brief (Insight, Ángulo, Gancho, Por qué ahora) de cada post de la semana. |
| `POST /articulo` | Brief y borrador SEO validado (palabras, h2, fuentes citadas, firma, FAQ). |
| `POST /portada` | Imagen principal y miniatura del artículo, sin texto. |
| `POST /archivos` | Lista o entrega logos y referencias de una marca. |

Reglas que aplica el código (no dependen de que el modelo obedezca): límites de caracteres, la
plantilla no se repite con la del post anterior, 3 titulares y elige uno, liga con UTM en su propia
línea, palabras prohibidas, disclaimer obligatorio si la marca lo pide, fuentes reales en research
e ideas, y si el modelo falla las reglas se le devuelve el error y se reintenta una vez.

Todo lo de la marca está en `marcas/<slug>/marca.json` y `ficha.md` (ver los comentarios de
`app/marcas.py`).

## Flujos de n8n

| # | Flujo | Cuándo | Qué hace |
|---|---|---|---|
| 01 | Alertas de error | Cuando falla otro flujo | Avisa en Telegram (Alertas) con flujo, nodo y error. |
| 02 | Aviso de reinicio | Cuando n8n arranca | Avisa que n8n se reinició. |
| 10 | Preparar posts (A y B) | Diario 10:07 / 12:07 | Posts «planeado» de hoy o mañana → redactar → pieza → Telegram «por aprobar». |
| 11 | Publicar posts (A y B) | Cada hora | Aprobados cuya hora llegó → Facebook → Instagram → Sheet → aviso. Nunca dos veces. |
| 12 | Telegram (respuestas) | Al tocar un botón o responder | Aprobar, pedir cambios, reintentar publicación, SEO, /start. |
| 13 | Nueva versión de post | Sub-flujo | Rehace según el alcance: misma imagen, imagen editada o pieza nueva. |
| 14 | Vigilante | Cada hora :40 | Posts atorados, caídas de n8n y recordatorios antes de la hora de publicación. |
| 20 | Research semanal | Lunes 8:00 | Tavily + Apify + DataForSEO → hallazgos y keywords. |
| 21 | Ideas semanales | Lunes 9:00 | Brief de cada post de los próximos 8 días con research, temporada y voz del público. |
| 30 | Leads | Webhook + cada 30 min | Formularios del sitio y de Meta → Sheet → Telegram; Conversions API para los del sitio. |
| 31 | Leads (preparar hoja) | Manual | Crea los encabezados de la pestaña Leads. |
| 40 | SEO (borradores) | Martes y jueves | Siguiente tema de `seo_articulos` → artículo + portada → borrador en Webflow → Telegram. |
| 41 | SEO acciones | Sub-flujo | ✅ publica en Webflow; ✏️ pide cambios y rehace el borrador. |
| 50 | Paid campañas (Meta) | Pestaña Paid del panel (webhook con token) | Crea campañas de Meta en pausa (7 objetivos), con pieza y texto; «probar» valida sin crear. |
| 51 | Meta Ads optimizador | Diario 10:40 | Pausa campañas «[Agente]» que rompen las reglas de costo por lead; propone lo demás; bitácora en `meta_ads_decisiones`. |
| 60 | Panel (lectura) | Webhook | Resumen para el panel (Sheet, seo_articulos, paid_campanas y meta_ads_decisiones). |
| 61 | Panel acciones | Webhook | Aprobar, pedir cambios o descartar desde el panel. |

## Estados de un post

```
planeado → preparando → por aprobar ──✅──► aprobado → publicando → publicado
                │            │  ▲
                │           ✏️  │ (nueva versión)
                │            ▼  │
                │      cambios pedidos
                ▼
        error al preparar            error al publicar (🔁 reintentar desde Telegram)
                                     descartado (desde el panel)
```

Aprobar desde Telegram o desde el panel cambia el estado; el que llega primero gana y el otro ya no
puede aprobar esa versión.
