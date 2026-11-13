# Agentes: qué hace cada uno y qué falta

Todos los agentes que existían en la agencia original ya vienen como flujo en `n8n/flujos/`, menos
el de WhatsApp. Aquí está la lógica de los que deciden algo, para que sepas qué esperar.

## Optimizador de Meta Ads (51) y botones ✅/❌ (54)

Pon el costo objetivo por lead de cada marca en el nodo «Configuración» de 51; mientras sea `null`
solo reporta. Corre diario a las 10:40.

Lee 7 días de cada cuenta de anuncios con una sola llamada en lote (`POST graph.facebook.com/` con
`batch`): conjuntos activos, anuncios activos, insights por día y de la semana. Decide por conjunto:

| Regla | Condición | Acción |
|---|---|---|
| Desastre | 0 leads y gasto ≥ 3 × costo objetivo | Pausar, aunque esté en aprendizaje |
| Aprendizaje | `learning_stage_info.status = LEARNING` | No tocar |
| Sin objetivo | La marca no tiene costo objetivo por lead | Solo reportar |
| 2× sin leads | 0 leads y gasto ≥ 2 × objetivo | Pausar |
| Costo alto | Costo por lead > 1.5 × objetivo y (≥ 5 leads o gasto ≥ 5 × objetivo) | Pausar |
| Costo bajo | Últimos 3 días: ≥ 3 leads y costo ≤ 0.8 × objetivo | Proponer +15 % de presupuesto (con tope), máximo una vez cada 3 días |
| Fatiga | Frecuencia > 3 y CTR de los últimos 3 días < 0.8 × CTR previo (≥ 1000 impresiones previas) | Pedir creativos nuevos |
| Pocos anuncios | Menos de 2 anuncios activos en el conjunto | Proponer variantes |

Reglas de seguridad:

- Solo **pausa solo** las campañas que creó el agente (nombre empieza con `[Agente]`); en las
  hechas a mano solo propone.
- **Subir presupuesto y pausar campañas hechas a mano llegan como pregunta** al tema Aprobaciones
  con ✅ Aplicar / ❌ No. Al tocar ✅, «Meta Ads acciones (botones)» (54) revisa que la propuesta
  siga vigente (estado «propuesta», de hace 2 días o menos, monto dentro del tope de MXN 300 al día,
  +20 % máximo, una subida cada 3 días por conjunto y que Meta no haya cambiado el presupuesto) y
  solo entonces la aplica. Edita el mensaje con el resultado y quita los botones.
- Si los encabezados de uso de la API pasan el 75 %, no aplica nada y avisa.
- Guarda cada decisión en la tabla `meta_ads_decisiones`.
- 51 y 54 tienen un disparador «Probar (simulación)» que corre todo sin aplicar ni guardar.

## Audiencias de Meta (53)

Webhook `agencia-paid-audiencias` (con el token del panel) o «Probar (listar)». Acciones:
`listar` (audiencias, formularios y posts recientes por marca), `crear` (audiencias base que falten)
y `similar` (similar 1 % del país a partir de otra). Audiencias base con prefijo `[Agente]`:
visitantes del sitio 30 y 180 días, dejaron datos (evento `Lead` del píxel), visitaron páginas clave
(`paginas_clave` en el nodo «Validar»), interacción con la página de Facebook y con Instagram, y
abrieron un formulario instantáneo. **No sube listas de clientes** hasta que tu aviso de privacidad
cubra ese uso.

## Analista semanal (70)

Lunes 8:30: GA4 (usuarios, sesiones, eventos que elijas, canales y páginas de entrada), Search
Console (clics, impresiones, posición, búsquedas) y Meta Ads (gasto, clics, leads, costo por lead),
semana contra la anterior. Un reporte por marca a Telegram (Reportes) con alertas si las sesiones
caen 30 % o más, si GA4 no registra visitas o si Meta gasta MXN 500+ sin leads.

## BigQuery (71, 72, 73)

- «BigQuery preparar (manual)» crea el dataset y las tablas `post_metrics_daily`,
  `social_account_daily` y `meta_ads_daily` (particionadas por día). Córrelo una vez.
- Diario 10:00: métricas de cada post de los últimos 14 días (alcance e interacciones de FB e IG),
  de las cuentas y de los anuncios de ayer. Si una carga falla, el flujo falla y avisa Alertas.
- Cada hora (:17): copia la pestaña Leads a la tabla `leads` **sin** nombre, correo, teléfono ni
  mensaje.

## SEO posiciones y on-page (42, 43)

- Lunes 7:43: posición en Google México (DataForSEO, top 30) de hasta 40 keywords por marca
  (artículos de `seo_articulos`, pestaña Keywords y `keywords_base`), con el cambio contra la semana
  anterior, y Search Console de la semana.
- Cada dos semanas (desde `BASE_ONPAGE`): revisión on-page de hasta 40 páginas por sitio (sitemap,
  artículos publicados y páginas con impresiones): título, descripción, H1, texto, velocidad,
  canonical, sitemap y CTR bajo. Claude propone hasta 5 cambios por marca a la pestaña «SEO
  propuestas» y a Telegram. **No aplica nada**: se aprueban o descartan en el panel (pestaña SEO) y
  se aplican a mano. Nunca revisa ni propone cambios en páginas legales.
- «Probar» corre todo, incluida la revisión on-page.

## Docs oficiales (74)

Domingo 6:13: lee con Tavily ~26 páginas oficiales de Meta Ads y Google Ads (lista en el nodo
«Fuentes»), guarda en tu repo (`GITHUB_REPO` → `docs-oficiales/`) solo lo que cambió, en un solo
commit, y manda a Telegram un análisis de Claude de lo que afecta a los agentes.

## Panel (62, 63, 64)

- 62 «Panel analytics (lectura)»: GA4, Search Console, alcance de la página e impresiones de
  anuncios de Meta, leads del Sheet y pestañas SEO. Alimenta Resultados, Analytics y SEO.
- 63 «Panel SEO»: marca propuestas como aprobadas o descartadas (solo las que siguen «propuesto»).
- 64 «Panel agentes»: flujos y corridas de las últimas 24 h de tu n8n (credencial «n8n API») y los
  issues con la etiqueta `encargo` de tu repo. «Encargar algo nuevo» abre un issue.

## Por armar: agente de WhatsApp

Responde en un número de WhatsApp Business (API oficial) con la ficha de la marca, captura leads al
Sheet, contesta preguntas frecuentes y escala a una persona. Usa un número separado del que se usa
para mensajes transaccionales. No viene en este repo porque depende del proveedor de WhatsApp.
