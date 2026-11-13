# Agentes por portar

Estos agentes existían en la agencia original pero no vienen como flujo en este repo, porque estaban
muy amarrados a sus cuentas o porque no se terminaron. Aquí está su lógica para que los
reconstruyas (con Claude y el MCP de n8n se arman en una sesión).

## Optimizador de Meta Ads (diario)

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
- **Subir presupuesto siempre es propuesta**: llega a Telegram con ✅/❌ y un segundo flujo
  («Meta Ads acciones») la aplica solo si sigue vigente (máximo +20 %, tope diario, una vez cada
  3 días, propuesta de máximo 2 días de antigüedad).
- Si los encabezados de uso de la API (`x-business-use-case-usage`, `x-ad-account-usage`,
  `x-app-usage`) pasan el 75 %, no aplica nada y avisa.
- Guarda cada decisión en una tabla `meta_ads_decisiones` (fecha, marca, campaña, conjunto,
  adset_id, regla, acción, estado, gasto_7d, leads_7d, cpl_7d, cpl_objetivo, frecuencia,
  presupuesto_dia, propuesta_presupuesto, detalle).
- Tiene un disparador «Probar (simulación)» que corre todo sin aplicar ni guardar.

## Audiencias de Meta

Por marca crea audiencias base con prefijo `[Agente]`: visitantes del sitio (30/180 días), los que
dejaron datos, interacción con la página de Facebook y la cuenta de Instagram, personas que
abrieron formularios instantáneos, y similares al 1 % en México. **No sube listas de clientes**
hasta que el aviso de privacidad cubra ese uso.

## Analista semanal

Lunes temprano: lee Google Analytics 4 (sesiones, conversiones por canal), Search Console (clics,
impresiones, posición) y Meta Ads (gasto, leads, costo por lead) de la semana contra la anterior, y
manda un reporte por marca a Telegram (Reportes) con 3 recomendaciones.

## BigQuery (embudo completo)

- Diario: métricas de cada post publicado (alcance, interacciones de FB e IG), de las cuentas y de
  los anuncios → dataset `marketing` (tabla particionada por día).
- Cada hora: copia la pestaña Leads a BigQuery **sin** nombre, correo ni teléfono.
- Con eso se arma el panel de embudo: qué fuente, campaña, keyword o post genera leads.

## SEO posiciones y on-page

- Semanal: posición de cada keyword de la tabla `Keywords` (DataForSEO SERP) con alerta cuando sube
  o baja.
- Cada dos semanas: revisión on-page de las páginas del sitio (título, meta, H1, enlaces internos,
  alt de imágenes). Claude **propone** los cambios al Sheet y a Telegram; no aplica nada solo.
  Nunca toca páginas legales.

## Documentación oficial al día

Domingo: lee con Tavily ~30 páginas oficiales de Meta Ads y Google Ads, guarda en el repo solo lo que
cambió y manda a Telegram un análisis de lo que afecta a los agentes.

## Agente de WhatsApp

Responde en un número de WhatsApp Business (API oficial) con la ficha de la marca, captura leads al
Sheet, contesta preguntas frecuentes y escala a una persona. Usa un número separado del que se usa
para mensajes transaccionales.
