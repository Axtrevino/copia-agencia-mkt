# Reglas de operación

Lo que aprendimos operando la agencia. Están puestas en los flujos y el código; cámbialas solo si
sabes por qué.

## Publicación

- **Nada se publica sin aprobación.** Ni posts ni artículos. No hay publicación automática por
  tiempo: si algo sigue sin aprobar, el Vigilante recuerda unas 3 h antes y en la última hora.
- **Nunca dos veces.** Antes de publicar se busca el `post_id` en «Publicados». Si Facebook salió y
  falló Instagram, no se reintenta solo para no duplicar.
- **Quien aprueba primero gana.** Telegram y el panel cambian el mismo estado; un botón viejo
  (otra versión, ya aprobado, ya publicado) no hace nada y explica por qué.
- Si una preparación falla, el post queda «error al preparar»; para reintentar, se vuelve a poner
  «planeado».

## Contenido

- Las cifras solo salen de «Datos verificados» de la ficha. El código no inventa ni redondea.
- Titulares claros: se entienden sin el copy ni la foto. El redactor propone 3 y elige el más claro.
- La plantilla no se repite con la del post anterior.
- Las ideas deben venir de una fuente real (competencia, temporada, voz del público) con su URL.
- En cambios, el alcance decide qué se rehace: solo copy → misma imagen; solo textos → se edita la
  imagen (más barato y conserva la foto); visual → pieza nueva.
- Si la industria tiene reglas legales (finanzas, salud, alcohol…), escríbelas en la ficha, como
  `palabras_prohibidas` y, si toda pieza debe llevar leyenda, con `disclaimer_obligatorio`.
- No se tocan páginas legales (privacidad, términos) con agentes.

## Campañas

- Se crean **en pausa**; una persona decide cuándo prenderlas y cuánto gastar.
- Tope de presupuesto diario por campaña en el flujo «Paid campañas» (`TOPE` en «Validar»).
- Pon un costo objetivo por lead por marca y bájalo con el tiempo.

## Operación

- Cada flujo tiene un tope de tiempo (Settings → Timeout) y «Alertas de error» como flujo de
  error: una corrida trabada no deja de avisar.
- Si n8n se detiene, el Vigilante lo detecta en su siguiente corrida (más de 2.5 h sin correr).
- Las alertas van por Telegram, también cuando el problema se resolvió solo.
