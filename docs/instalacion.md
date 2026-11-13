# Instalación

Tiempo aproximado: una tarde. Puedes pedirle a Claude (con acceso a tu n8n por MCP) que haga los
pasos 5 a 7 por ti.

## 1. Cuentas

| Servicio | Para qué | Costo aproximado |
|---|---|---|
| Anthropic | Claude arma las propuestas de campaña en la pestaña Paid (si no hay llave, lo hace GPT) | Por uso |
| OpenAI | Texto (GPT) e imágenes (GPT Image) | Por uso; una pieza en calidad alta cuesta centavos de dólar |
| Modal | Correr el servicio `app/` | Por segundo; trae saldo gratis cada mes |
| n8n | Flujos | n8n Cloud o tu propio servidor |
| Google | Sheet | Gratis |
| Telegram | Aprobaciones y avisos | Gratis |
| Meta for Developers | Publicar en Facebook/Instagram, leads, Conversions API, campañas | Gratis (las campañas sí cuestan) |
| Google Cloud | GA4, Search Console y BigQuery con una cuenta de servicio (Analytics, Resultados, SEO, Analista, BigQuery) | Gratis hasta cierto uso; BigQuery cobra por consulta |
| GitHub | Encargos del panel y copia de los docs oficiales | Gratis |
| DataForSEO | Casi obligatoria para SEO: escoger los temas del blog con datos, medir posiciones y revisar páginas | Por uso |
| Opcionales | Tavily (noticias y docs oficiales), Apify (competencia), Webflow (blog) | Por uso |

## 2. Tu marca

1. Copia `marcas/marca-a/` (y `marca-b/` si tienes dos marcas). Si cambias el nombre de la
   carpeta, cambia también `marca-a` en los flujos (búscalo en n8n).
2. Llena `marca.json`: colores y reglas visuales (en inglés, van al prompt de imagen), plantillas,
   liga del sitio con UTM, palabras prohibidas, temporadas de tu industria y la sección `blog`.
3. Llena `ficha.md`: entre más concreta, mejor el contenido. «Datos verificados» es la única fuente
   de cifras.
4. Pon los logos en `logos/` con los nombres que usan las plantillas.

## 3. Servicio en Modal

```
pip install modal
modal token new
modal secret create agencia-marketing OPENAI_API_KEY=… ANTHROPIC_API_KEY=… PIEZA_TOKEN=<inventa uno largo>
modal deploy app/main.py
```

La URL que imprime (`https://<cuenta>--agencia-marketing-pieza.modal.run`) es tu `MODAL_URL`.
Prueba: `curl <MODAL_URL>/salud` → `{"ok": true}`.

Para que se despliegue solo al hacer merge a `main`, agrega `MODAL_TOKEN_ID` y
`MODAL_TOKEN_SECRET` en GitHub → Settings → Secrets → Actions.

## 4. Google Sheet y Telegram

1. Crea el Sheet con las pestañas de [hoja-de-calculo.md](hoja-de-calculo.md).
2. Crea un bot con @BotFather y un grupo con **temas** (Aprobaciones, Reportes, Alertas, en ese
   orden). Mete al bot como administrador.
3. Saca el `chat_id` del grupo (empieza con `-100`), los números de los temas (normalmente 2, 3 y
   4) y tu user id (@userinfobot).

## 5. Credenciales en n8n

Crea estas credenciales con **exactamente** estos nombres (los flujos los buscan así):

| Nombre | Tipo | Valor |
|---|---|---|
| Google Sheets | Google Sheets OAuth2 | Tu cuenta de Google |
| Telegram (bot de la agencia) | Telegram API | Token de @BotFather |
| Modal (X-Pieza-Token) | Header Auth | Name `X-Pieza-Token`, Value = tu `PIEZA_TOKEN` |
| Panel (X-Panel-Token) | Header Auth | Name `X-Panel-Token`, Value = otro token que inventes |
| Meta página A / Meta página B | Facebook Graph API | Token de página (publicar, leer formularios) |
| Meta Ads A / Meta Ads B | Facebook Graph API | Token de sistema con `ads_management` (CAPI y campañas) |
| Tavily (Authorization: Bearer) | Header Auth | `Authorization: Bearer <llave>` |
| Apify (Authorization: Bearer) | Header Auth | `Authorization: Bearer <token>` |
| DataForSEO | HTTP Basic Auth y DataForSEO API | Usuario y contraseña de la API |
| Webflow | Webflow API | Token del sitio con permiso de CMS y Assets |
| Google (cuenta de servicio) | Google Service Account API | JSON de una cuenta de servicio con los alcances `analytics.readonly`, `webmasters.readonly` y `bigquery`. Agrégala como lector en GA4 (Admin → Acceso a la propiedad) y como usuario en Search Console; dale «BigQuery Job User» y «Data Editor» en tu proyecto |
| Anthropic | Anthropic API | Llave de Anthropic (propuestas SEO y análisis de docs oficiales) |
| GitHub | GitHub API | Token de acceso fino con permiso de *Contents* e *Issues* (lectura y escritura) solo en tu repo |
| n8n API | n8n API | Llave de tu n8n (Settings → n8n API) y la URL de tu n8n; la usa la pestaña Agentes |

Nunca pegues llaves en los flujos ni en el repo: solo en credenciales de n8n y secretos de Modal.

## 6. Importar los flujos

1. En n8n → Data tables crea `seo_articulos`, `paid_campanas` y `meta_ads_decisiones` (columnas en
   [hoja-de-calculo.md](hoja-de-calculo.md)) y copia sus IDs.
2. `cp n8n/config.ejemplo.json n8n/config.json`, llénalo y corre `python3 n8n/configurar.py`.
3. Importa `n8n/listos/`:
   - **Con la línea de comandos de n8n** (respeta los IDs y las referencias entre flujos):
     `n8n import:workflow --separate --input=n8n/listos`
   - **Desde la pantalla** (Workflows → Import from file, uno por uno): n8n les pone IDs nuevos.
     Corre `python3 n8n/configurar.py --ids` y reconecta los nodos que lista («From list») y el
     *Error workflow* de cada flujo.
4. Abre cada flujo y revisa que las credenciales quedaron asignadas (los nodos HTTP a veces no se
   asignan solos).
5. En «Agencia · Leads» cambia los dominios de `DOMINIOS` si no usaste `config.json`.
6. Corre una vez, a mano: «Leads (preparar hoja)», «SEO preparar pestañas» y «BigQuery preparar».
7. En «Panel analytics (lectura)» → nodo «Configuración» pon el evento de GA4 que cuenta como lead
   (`generate_lead` por omisión) y, si tienes, un paso intermedio del embudo (`form_start`).
   En «SEO posiciones y on-page» y en «SEO plan de artículos» → nodo «Marcas» escribe el público y
   las reglas de cada marca; en el plan, además, 5 a 20 semillas (qué vende y qué problemas tiene su
   público) y 2 o 3 dominios de la competencia, y marca `blog: true` en las marcas con blog.
8. Activa primero: Alertas de error, Telegram (respuestas) y Vigilante. Luego Preparar y Publicar.
   Los agentes de análisis (Analista, BigQuery, SEO posiciones, Docs oficiales) se activan cuando
   ya estén sus credenciales.

## 7. Meta

- Página de Facebook con Instagram profesional ligado.
- App de Meta en modo Live con permisos `pages_manage_posts`, `pages_read_engagement`,
  `instagram_basic`, `instagram_content_publish`, `leads_retrieval` y, para campañas y CAPI,
  `ads_management`. Para métricas (BigQuery diario, panel) agrega `read_insights` e
  `instagram_manage_insights` al token de página.
- Las audiencias que crea «Audiencias de Meta» necesitan el píxel en el sitio y aceptar los términos
  de públicos personalizados en el Administrador de anuncios. No sube listas de clientes.
- En tu sitio, manda los formularios al webhook `https://<tu-n8n>/webhook/agencia-leads` con
  `navigator.sendBeacon` (campo `d` con JSON: `campos`, `pagina`, `atribucion`, `event_id`, `fbp`,
  `fbc`). Usa el mismo `event_id` en el píxel para que Meta no cuente doble.

## 8. Panel

Abre `panel/index.html` (o súbelo a cualquier hosting estático) → Conexión → URL de tu n8n y el
valor de «Panel (X-Panel-Token)». Activa en n8n «Panel (lectura)», «Panel acciones», «Paid propuesta», «Paid campañas (Meta)», «Panel analytics (lectura)», «Panel SEO (aprobar propuestas)» y «Panel agentes (lectura y encargos)»; todos usan la credencial «Panel (X-Panel-Token)». Si falta alguno de los tres últimos, su pestaña dice qué conectar en vez de romperse. En la pestaña Paid las campañas se crean en pausa; prenderlas es lo único que gasta.

## Primera prueba

1. En el Sheet agrega un post de `marca-a` con fecha de hoy, hora dentro de 2 horas y estado
   `planeado`.
2. En n8n abre «Preparar posts (Marca A)» → Execute workflow.
3. En 2–3 minutos llega la pieza a Telegram. Toca ✏️, pide un cambio, y luego ✅.
4. A la hora del post, «Publicar posts» lo sube a Facebook e Instagram y avisa en Reportes.
