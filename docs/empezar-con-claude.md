# Empezar con Claude

La forma más fácil de instalar la agencia es pedirle a Claude que te lleve de la mano. Antes, lee
esto (10 minutos).

## Cuentas que vas a necesitar

Claude te guía para abrir y configurar cada una; aquí solo es para que sepas qué es cada cosa.

| Cuenta | Para qué sirve | ¿Obligatoria? |
|---|---|---|
| **n8n** | Es el «motor»: ahí viven y corren todos los agentes (preparar posts, publicar, leads, reportes). | Sí |
| **Modal** | Es el servidor donde vive el programa de la carpeta `app/`. Ese programa carga las reglas y logos de tu marca, le pide a la IA los textos y las imágenes, revisa el resultado y deja la pieza lista para publicar. n8n lo llama a cualquier hora, aunque nadie esté conectado. Sin él no se produce contenido. | Sí |
| **OpenAI** | La IA que usa Modal para escribir los posts y crear las imágenes. | Sí |
| **Anthropic (Claude)** | Arma las propuestas de campañas, escoge los temas del blog, propone cambios de SEO y revisa cambios en la documentación de Meta y Google. | Sí |
| **Google (Sheet)** | El Google Sheet es el calendario de posts, la lista de leads y la bitácora de SEO. | Sí |
| **Google Cloud** | Permite leer Google Analytics 4 y Search Console para el panel y los reportes, y guardar el histórico en BigQuery. | Recomendada |
| **Telegram** | Ahí te llegan los posts para aprobar (✅ / ✏️), los reportes y las alertas. | Sí |
| **Meta for Developers** | Publica en Facebook e Instagram, recibe los leads de los formularios y crea campañas (siempre en pausa). | Sí |
| **Tu sitio web** (donde viva: WordPress, Webflow, Cloudflare Pages, Wix, Shopify…) | Hay que ponerle la etiqueta de Google Analytics y el píxel de Meta, y conectar sus formularios a n8n para que los leads lleguen solos. Los artículos del blog se publican automáticamente solo si el sitio está en Webflow; en otra plataforma, Claude adapta ese paso o te deja los artículos listos para pegar. | Sí |
| **DataForSEO** | Escoge los temas del blog con datos reales de búsqueda, mide en qué posición sales en Google y revisa tus páginas. | Casi obligatoria si quieres hacer SEO |
| **GitHub** | Guarda tus cambios (marca, ajustes) para poder regresar a una versión anterior; además, los encargos del panel y la copia de la documentación oficial. | Opcional (recomendada) |
| **Tavily** | Busca noticias de tu industria y lee la documentación oficial. | Opcional |
| **Apify** | Revisa los anuncios y publicaciones de tu competencia. | Opcional |

## Antes de escribirle a Claude

1. Usa Claude Code o el escritorio de Claude.
2. Dale el repo: clónalo o descárgalo en tu compu, o conecta GitHub.
3. Si ya tienes n8n, conéctalo a Claude por MCP (en n8n: *Settings → MCP access*). Si no sabes
   cómo, Claude te guía.
4. **Las llaves y tokens nunca van en el chat.** Tú los pegas directo en las credenciales de n8n y
   en los secretos de Modal; Claude te dice cuáles y con qué nombre.

## El prompt

```
Quiero instalar la agencia de marketing del repo https://github.com/Axtrevino/copia-agencia-mkt
para mi negocio. No soy técnico: llévame de la mano en cada paso, con instrucciones de clic
por clic, y espera a que te confirme antes de seguir.

1. Cuentas: revisa docs/empezar-con-claude.md y docs/instalacion.md y dime cuáles necesito según
   lo que quiero usar. Guíame para abrir y configurar cada una (n8n, Modal, OpenAI, Anthropic,
   Google Sheet, Google Cloud con cuenta de servicio, bot y grupo de Telegram con temas, app de
   Meta con mi página e Instagram, DataForSEO y las opcionales que elija). Dime para qué sirve
   cada una y qué permisos activar.
2. Mi sitio: pregúntame dónde vive mi sitio web. Guíame para poner la etiqueta de GA4 y el
   píxel de Meta, y para mandar mis formularios al webhook de leads. Si mi sitio no está en
   Webflow, adapta la publicación del blog (flujos 40 y 41) a mi plataforma o déjame los
   artículos listos para pegar.
3. Conexión: si todavía no conecto mi n8n contigo por MCP, guíame para hacerlo.
4. Mi marca: hazme preguntas sobre mi negocio, qué vendo, a quién, en qué país o ciudad, mi tono,
   colores, reglas y 2 o 3 sitios de mi competencia. Llena marcas/marca-a (y marca-b si tengo
   otra marca) y el nodo «Marcas» de «SEO plan de artículos» y de «SEO posiciones y on-page».
5. Datos: pídeme uno por uno los IDs que necesitas (Sheet, páginas, cuentas de anuncios,
   GA4, Search Console, Telegram) y dime dónde encontrar cada uno.
6. Llaves: nunca me pidas llaves ni tokens en el chat. Dime qué credencial crear en n8n,
   con qué nombre exacto y dónde pegarla, y cómo poner los secretos en Modal.
7. Instalación: llena n8n/config.json, corre python3 n8n/configurar.py, despliega el
   servicio en Modal, crea las Data tables, importa n8n/listos/ a mi n8n y revisa que cada
   nodo tenga su credencial. Corre una vez los flujos manuales (Leads preparar hoja,
   SEO preparar pestañas, BigQuery preparar) y «SEO plan de artículos» con «Probar».
8. Encendido: activa primero Alertas de error, Telegram (respuestas) y Vigilante. Haz
   conmigo la primera prueba de docs/instalacion.md. No actives nada que publique o gaste
   dinero sin mi OK.
9. Panel: conéctame panel/index.html y dime qué pestañas ya tienen datos y qué falta.
```

## Qué esperar

- Ningún flujo publica ni gasta sin tu aprobación: los posts y artículos llegan a Telegram para
  ✅, y las campañas se crean en pausa.
- La primera semana es normal ajustar algún nodo: pídeselo a Claude con el error que te llegue a
  Telegram (tema Alertas).
- El agente de WhatsApp no viene incluido.
