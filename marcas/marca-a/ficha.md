# Ficha de marca: Marca A

> Plantilla. Copia la carpeta `marcas/marca-a/` a `marcas/<tu-marca>/` y reemplaza todo.
> Esta ficha la leen el redactor de posts, el de artículos, Research e Ideas. Entre más concreta,
> mejor sale el contenido. Lo que no esté aquí, la IA lo inventa.

## 1. Qué es la marca
- Qué vende, a quién y en qué ciudades o país.
- Qué problema resuelve, en una frase que diría un cliente.
- Por qué la eligen frente a las alternativas (3 razones, con pruebas si las hay).

## 2. Público objetivo
- Quién compra (rol, edad, ocupación, tamaño de empresa si es B2B).
- Qué le preocupa, con sus palabras.
- Dónde está (redes, lugares, momentos del día).
- Qué objeciones tiene antes de comprar.

## 3. Voz y tono
- 3 adjetivos de la voz (p. ej. cercana, clara, sin rodeos).
- Tú o usted.
- Palabras SÍ: …
- Palabras NO: … (también se pueden poner en `palabras_prohibidas` de `marca.json` para que el
  código las bloquee)

## 4. Productos o servicios
- Nombre, para quién es y qué incluye cada uno.
- Lo que NO hace la marca (para que la IA no lo prometa).

## 5. Tipos de post
- educativo: enseña algo útil del giro.
- captacion: invita a dejar datos o a escribir; puede llevar CTA y URL en la imagen.
- marca: cultura, equipo, historia.
- prueba_social: casos o reseñas reales (nunca inventados).

## 6. Hashtags y CTAs
- Hashtags permitidos: #… #… (máximo 3 por post).
- CTAs permitidos: «Conoce más», «Escríbenos», …

## 7. Sitio y ligas
- Sitio: https://www.marca-a.com/ (la liga con UTM la agrega el código; ver `liga` en marca.json).

## 8. Competencia
- Competidor 1 (sitio, qué promete, de qué se queja su público).
- Competidor 2 …
- Nunca se nombra a la competencia en los posts.

## 9. Reglas legales o de la industria
- Lo que la ley o la industria no permite decir (promesas, cifras sin leyenda, etc.).
- Si toda pieza debe llevar una leyenda legal, ponla como `disclaimer` en «Datos verificados» y
  pon `"disclaimer_obligatorio": true` en marca.json.

## Datos verificados
Única fuente de cifras para posts y artículos. Formato `- clave: valor`. Si un dato cambia, se
cambia solo aquí.
- precio_desde: $000 MXN (ejemplo)
- cobertura: Ciudad de México y área metropolitana (ejemplo)
- revisor: Nombre Apellido, puesto (firma de los artículos; si se deja vacío no se firma)
