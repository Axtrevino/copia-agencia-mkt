# Agencia de marketing con agentes

Una agencia de marketing que corre con agentes de IA. Prepara los posts de redes, los manda a
aprobar por Telegram y los publica en Facebook e Instagram. También investiga a la competencia,
propone ideas cada semana, escribe artículos SEO, junta los leads, crea campañas de Meta en pausa y
muestra todo en un panel. **Nada se publica sin aprobación humana.**

Sirve para cualquier industria: la marca, su voz y sus reglas viven en archivos de configuración,
no en el código. Viene con dos espacios de marca (`marca-a` y `marca-b`) listos para llenar.

## Qué trae

| Carpeta | Qué es |
|---|---|
| `app/` | El servicio (Python en [Modal](https://modal.com)): redacta posts, hace las piezas con GPT Image, edita textos de una pieza, resume el research, propone ideas y escribe artículos SEO con su portada. |
| `marcas/` | Una carpeta por marca: `marca.json` (reglas que aplica el código), `ficha.md` (voz, público, producto, datos), `ajustes.md`, logos y piezas de referencia. |
| `n8n/` | 18 flujos de [n8n](https://n8n.io) que mueven todo: calendario → preparar → aprobar → publicar, vigilante, leads, research, ideas, SEO, campañas de Meta y el panel. |
| `panel/` | Panel web (un solo HTML) para ver leads, posts, artículos y research, y aprobar o pedir cambios. |
| `docs/` | Arquitectura, instalación paso a paso, estructura del Google Sheet, reglas de operación y agentes por portar. |
| `tests/` | Pruebas del servicio (`pytest`). |

## Cómo funciona (en corto)

```
Google Sheet «Calendario» ──► n8n «Preparar posts» ──► Modal /redactar + / (pieza)
                                                         │
                                Telegram (✅ / ✏️) ◄──────┘
                                     │
          ✏️ cambios ──► «Nueva versión» (copy / textos / imagen)
          ✅ aprobado ──► «Publicar posts» a su hora ──► Facebook + Instagram ──► Sheet «Publicados»
```

Más detalle en [docs/arquitectura.md](docs/arquitectura.md).

## Empezar

1. Lee [docs/instalacion.md](docs/instalacion.md): cuentas que necesitas, Google Sheet, bot de
   Telegram, Modal, n8n y Meta.
2. Copia `marcas/marca-a/` y llena tu marca (ver [marcas/marca-a/ficha.md](marcas/marca-a/ficha.md)).
3. Despliega el servicio: `modal deploy app/main.py`.
4. Llena `n8n/config.json` y corre `python3 n8n/configurar.py`; importa `n8n/listos/` en tu n8n.
5. Abre `panel/index.html` y conéctalo a tu n8n.

## Reglas que trae puestas

- Ningún post ni artículo se publica sin ✅ de una persona. Si algo sigue sin aprobar cerca de su
  hora, el Vigilante recuerda; nunca publica solo.
- Un post nunca se publica dos veces (se revisa contra «Publicados» antes de publicar).
- Las campañas de Meta se crean **en pausa** y con tope de presupuesto diario.
- Las cifras de la marca salen solo de «Datos verificados» de la ficha.

Ver [docs/reglas-operacion.md](docs/reglas-operacion.md).

## Desarrollo

```
make install   # pip install -e ".[dev]"
make check     # ruff + pytest
make deploy    # modal deploy app/main.py
```

## Licencia

Úsalo y modifícalo como quieras.
