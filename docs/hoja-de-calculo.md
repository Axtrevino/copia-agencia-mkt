# Google Sheet

Un solo Sheet con estas pestañas. La primera fila son los encabezados, exactamente como aparecen
aquí (en minúsculas y sin acentos). Comparte el Sheet con la cuenta de Google que conectes en n8n.

## Calendario

Una fila por post. Todas las marcas en la misma pestaña; la columna `marca` dice de quién es.

| Columna | Quién la llena | Notas |
|---|---|---|
| `post_id` | Persona | Único. Formato `PREFIJO-RED-AAAA-MMDD-N`, en mayúsculas, p. ej. `MA-FB-2027-0115-1`. El prefijo debe ser letras (lo usa Telegram para reconocer el post). |
| `marca` | Persona | El slug de la carpeta en `marcas/` (`marca-a`, `marca-b`…). |
| `fecha` | Persona | `AAAA-MM-DD`. |
| `hora` | Persona | `HH:mm`, hora de la Ciudad de México. |
| `tipo` | Persona | `educativo`, `captacion`, `marca`, `prueba_social` (o los que definas en la ficha). |
| `tema` | Persona o Ideas | Brief del post. Ideas lo llena los lunes si no empieza con «Insight:». |
| `estado` | Flujos | Ver estados en `docs/arquitectura.md`. Pon `planeado` para que se prepare. |
| `version` | Flujos | Sube con cada versión. |
| `sistema`, `escena`, `kicker`, `titular`, `palabra_acento`, `subtitulo`, `cta`, `url`, `disclaimer`, `copy` | Flujos | Lo que escribió el redactor. |
| `imagen_url` | Flujos | `tg:<file_id>`: la pieza vive en Telegram. |
| `costo_usd` | Flujos | Costo estimado de la imagen. |
| `cambios_pedidos` | Flujos | Último cambio pedido. |
| `tg_msg` | Flujos | Mensaje de Telegram de la versión por aprobar (para responderle en los recordatorios). |
| `fb_url`, `ig_url` | Flujos | Ligas de lo publicado. |
| `actualizado` | Flujos | Última modificación. |

## Publicados

`fecha_hora`, `post_id`, `marca`, `red`, `liga`, `costo_usd`. Antes de publicar, el flujo revisa
aquí que el `post_id` no esté: así nunca se publica dos veces.

## Leads

Corre una vez «Agencia · Leads (preparar hoja, manual)» para crear los encabezados:
`lead_id fecha marca origen estado nombre telefono correo empresa mensaje tipo detalle pagina
landing referrer utm_source utm_medium utm_campaign utm_content utm_term gclid fbclid fbp fbc
event_id notas actualizado`.

## Hallazgos

`fecha semana marca tipo hallazgo fuente accion confianza`

## Keywords

`fecha marca keyword intencion prioridad volumen cpc estado`

## Tablas de n8n (Data tables)

Créalas en n8n → Data tables.

**seo_articulos**: `marca`, `orden` (número), `tema`, `keyword`, `intencion`, `estado` (pon
`planeado`), `version` (número), `titulo`, `slug`, `meta`, `webflow_item_id`, `imagen_url`, `url`,
`volumen` (número), `cpc` (número), `dificultad` (número), `palabras` (número), `notas`,
`cambios`, `error`, `actualizado`.

**meta_ads_decisiones** (bitácora del optimizador): `fecha`, `marca`, `campana`, `conjunto`,
`adset_id`, `regla`, `accion`, `estado`, `gasto_7d`, `leads_7d`, `cpl_7d`, `cpl_objetivo`,
`frecuencia`, `presupuesto_dia`, `propuesta_presupuesto`, `detalle`.

**paid_campanas**: `campana_id`, `marca`, `medio`, `nombre`, `estado`, `objetivo`,
`presupuesto`, `propuesta`, `landing`, `titular`, `copy`, `imagen`, `meta_campaign_id`,
`meta_adset_id`, `meta_creative_id`, `meta_ad_id`, `costo_usd`, `error`, `actualizado`.
