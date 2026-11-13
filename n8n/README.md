# Flujos de n8n

Los JSON de `flujos/` están limpios: sin credenciales, sin IDs de cuentas y con marcadores
`__ASI__` donde va tu información. Para dejarlos listos:

```
cp n8n/config.ejemplo.json n8n/config.json   # llénalo
python3 n8n/configurar.py                    # escribe n8n/listos/
```

Luego importa `n8n/listos/` (pasos en [../docs/instalacion.md](../docs/instalacion.md)).

| Archivo | Flujo |
|---|---|
| 01 | Alertas de error (flujo de error de todos) |
| 02 | Aviso de reinicio de n8n |
| 10 | Preparar posts (uno por marca; cambia el nodo «Config») |
| 11 | Publicar posts (uno por marca; cambia el nodo «Config» y la credencial de Meta) |
| 12 | Telegram (respuestas): aprobar, cambios, reintentar, SEO |
| 13 | Nueva versión de post (sub-flujo) |
| 14 | Vigilante |
| 20 | Research semanal (edita el nodo «Marcas») |
| 21 | Ideas semanales (edita el nodo «Marcas») |
| 30 | Leads (sitio + formularios de Meta + Conversions API) |
| 31 | Leads: crear encabezados (manual) |
| 40 | SEO borradores en Webflow (edita «Preparar pedido») |
| 41 | SEO acciones (publicar o pedir cambios) |
| 50 | Paid campañas de Meta (en pausa, con tope diario) |
| 52 | Paid propuesta (Claude arma la campaña que escribes en el panel) |
| 51 | Meta Ads optimizador (pon el costo objetivo por lead en «Configuración») |
| 60 | Panel (lectura) |
| 61 | Panel acciones |

**Otra marca:** duplica 10 y 11, cambia `marca`, `nombre`, `page_id` e `ig_id` en «Config» y la
credencial de Meta; agrégala en 20, 21, 30 y 40 y en el nodo «Publicar de nuevo» de 12.
