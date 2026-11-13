# Instrucciones para agentes (Claude, Codex, etc.)

- Idioma del código, comentarios y mensajes: español.
- Todo lo de una marca vive en `marcas/<slug>/`. No escribas nombres, cifras, dominios ni reglas
  de una marca en `app/`.
- Nunca pegues llaves ni tokens en código, flujos, docs o chat. Van en secretos de Modal y
  credenciales de n8n.
- Ningún flujo publica, gasta o borra sin aprobación humana. No agregues publicación automática
  por tiempo.
- Antes de terminar: `ruff check . && ruff format --check . && pytest`.
- Flujos de n8n: los JSON de `n8n/flujos/` usan marcadores `__ASI__`; `n8n/configurar.py` los
  llena. Si agregas un marcador, agrégalo a `n8n/config.ejemplo.json`.
- Lógica nueva del servicio: funciones puras probadas en `tests/`; lo externo (OpenAI, red) se
  inyecta.
