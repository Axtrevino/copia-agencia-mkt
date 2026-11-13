"""Modal: el servicio de la agencia que llaman los flujos de n8n.

n8n hace POST a la URL de la función `pieza` con el JSON del pedido y el header `X-Pieza-Token`.
Endpoints:
  POST /           GPT Image hace la pieza completa (con logos y referencias de la marca)
  POST /redactar   GPT escribe o corrige la idea del post (escena, textos, copy)
  POST /editar     cambia solo los textos de una pieza ya hecha (sin rehacer la foto)
  POST /research   resume los datos de la semana en hallazgos y keywords
  POST /ideas      el tema (brief) de cada post desde competencia, temporada y público
  POST /articulo   brief y borrador de un artículo SEO (sin publicar)
  POST /portada    imagen principal y miniatura de un artículo (sin texto)
  POST /archivos   lista o entrega los logos y referencias de una marca
  GET  /salud

Secretos en Modal → Secrets → `agencia-marketing`: `OPENAI_API_KEY` y `PIEZA_TOKEN` (opcionales:
`PIEZA_MODELO`, `PIEZA_TAMANO`, `PIEZA_CALIDAD`, `EDITAR_FIDELIDAD`, `PIEZA_TEXTO_MODELO`,
`PORTADA_CALIDAD`). La carpeta `marcas/` viaja dentro de la imagen.

Deploy:  modal deploy app/main.py   (o el workflow de GitHub al fusionar a main)
"""

from __future__ import annotations

import os

import modal

APP_NAME = os.environ.get("APP_NAME", "agencia-marketing")
SECRET = os.environ.get("MODAL_SECRET", "agencia-marketing")

app = modal.App(APP_NAME)

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install_from_pyproject("pyproject.toml")
    .pip_install("fastapi[standard]")
    .add_local_dir("marcas", "/marcas")
    .add_local_python_source("app")
)


@app.function(
    image=image,
    secrets=[modal.Secret.from_name(SECRET)],
    timeout=400,
    max_containers=2,
)
@modal.asgi_app()
def pieza():
    from fastapi import FastAPI, Header, HTTPException

    from app import marcas
    from app.datos import datos_verificados, seccion
    from app.imagen import Referencia, editar, generar
    from app.pieza import PedidoMalo, archivos_de
    from app.research import ErrorHTTP
    from app.servicio import atender, atender_edicion, token_valido

    web = FastAPI(title="agencia-marketing")
    llave = os.environ.get("OPENAI_API_KEY", "")
    modelo_imagen = os.environ.get("PIEZA_MODELO", "gpt-image-2")
    tamano = os.environ.get("PIEZA_TAMANO", "1088x1360")
    calidad = os.environ.get("PIEZA_CALIDAD", "high")
    modelo_texto = os.environ.get("PIEZA_TEXTO_MODELO", "gpt-5.5")

    def revisar_token(token):
        if not token_valido(token, os.environ.get("PIEZA_TOKEN")):
            raise HTTPException(status_code=401, detail="token inválido")

    def ajustes(marca: str) -> str:
        return marcas.leer(marca, "ajustes.md").strip()

    def referencias(marca: str, sistema: str) -> list[Referencia]:
        base = marcas.directorio(marca)
        rutas = [base / r for r in archivos_de(marca, sistema)]
        faltan = [r.name for r in rutas if not r.exists()]
        if faltan or not rutas:
            # Sin logo oficial GPT Image lo inventaría: no se gasta la imagen.
            raise HTTPException(
                status_code=422, detail=f"faltan archivos de {marca}: {', '.join(faltan) or 'logo'}"
            )
        return [Referencia(r.name, r.read_bytes()) for r in rutas]

    def http(fn):
        """Corre la lógica y traduce sus errores a HTTP (los de OpenAI no traen la llave)."""
        try:
            return fn()
        except (PedidoMalo, marcas.MarcaDesconocida) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
        except ErrorHTTP as exc:
            if exc.codigo == 502:
                print(f"falló: {exc.detalle}")
            raise HTTPException(status_code=exc.codigo, detail=exc.detalle) from None
        except RuntimeError as exc:
            print(f"falló: {exc}")
            raise HTTPException(status_code=502, detail=str(exc)) from None

    @web.post("/")
    def crear(pedido: dict, x_pieza_token: str | None = Header(default=None)) -> dict:
        revisar_token(x_pieza_token)
        marca = str(pedido.get("marca") or "")
        sistema = str(pedido.get("sistema") or "")

        def correr():
            refs = referencias(marca, sistema)
            imagen_ajustes = seccion(ajustes(marca), "Imagen")

            def pedir(prompt, refs_):
                return generar(prompt, llave, refs_, modelo_imagen, tamano, calidad)

            return atender(pedido, pedir, refs, imagen_ajustes)

        resultado = http(correr)
        print(f"pieza {resultado['archivo']}: costo {resultado['costo_usd']}")
        return resultado

    @web.post("/redactar")
    def redactar_idea(pedido: dict, x_pieza_token: str | None = Header(default=None)) -> dict:
        from app.redactor import redactar

        revisar_token(x_pieza_token)
        marca = str(pedido.get("marca") or "")
        idea = http(
            lambda: redactar(
                marcas.ficha(marca), pedido, llave, modelo=modelo_texto, ajustes=ajustes(marca)
            )
        )
        version = int(pedido.get("version") or 0)
        if str(pedido.get("cambios") or "").strip() or version < 1:
            version += 1
        return {"marca": marca, "post_id": pedido.get("post_id"), "version": version, **idea}

    @web.post("/editar")
    def editar_pieza(pedido: dict, x_pieza_token: str | None = Header(default=None)) -> dict:
        revisar_token(x_pieza_token)
        marca = str(pedido.get("marca") or "")

        def pedir_edicion(prompt, actual):
            return editar(
                prompt,
                llave,
                actual,
                modelo=modelo_imagen,
                tamano=tamano,
                calidad=calidad,
                fidelidad=os.environ.get("EDITAR_FIDELIDAD", "high"),
            )

        def correr():
            datos = datos_verificados(marcas.ficha(marca))
            return atender_edicion(pedido, pedir_edicion, datos=datos or None)

        return http(correr)

    @web.post("/research")
    def research(pedido: dict, x_pieza_token: str | None = Header(default=None)) -> dict:
        from app.research import atender as atender_research

        return http(
            lambda: atender_research(
                pedido, x_pieza_token, os.environ.get("PIEZA_TOKEN"), llave, modelo_texto
            )
        )

    @web.post("/ideas")
    def ideas(pedido: dict, x_pieza_token: str | None = Header(default=None)) -> dict:
        from app.ideas import atender as atender_ideas

        return http(
            lambda: atender_ideas(
                pedido, x_pieza_token, os.environ.get("PIEZA_TOKEN"), llave, modelo_texto
            )
        )

    @web.post("/articulo")
    def articulo(pedido: dict, x_pieza_token: str | None = Header(default=None)) -> dict:
        from app.articulo import atender as atender_articulo

        return http(
            lambda: atender_articulo(
                pedido, x_pieza_token, os.environ.get("PIEZA_TOKEN"), llave, modelo_texto
            )
        )

    @web.post("/portada")
    def portada(pedido: dict, x_pieza_token: str | None = Header(default=None)) -> dict:
        from app.portada import TAMANO
        from app.portada import atender as atender_portada

        def pedir_portada(prompt):
            return generar(
                prompt,
                llave,
                modelo=modelo_imagen,
                tamano=TAMANO,
                calidad=os.environ.get("PORTADA_CALIDAD", "medium"),
            )

        return http(
            lambda: atender_portada(
                pedido, x_pieza_token, os.environ.get("PIEZA_TOKEN"), pedir_portada
            )
        )

    @web.post("/archivos")
    def archivos(pedido: dict, x_pieza_token: str | None = Header(default=None)) -> dict:
        """Lista (o entrega uno, con `nombre`) los logos y referencias de una marca."""
        import base64
        import hashlib

        revisar_token(x_pieza_token)
        marca = str(pedido.get("marca") or "")
        rutas = http(
            lambda: {
                f"{c}/{r.name}": r
                for c in ("logos", "referencias")
                for r in marcas.archivos(marca, c)
            }
        )
        nombre = str(pedido.get("nombre") or "")
        if not nombre:
            lista = []
            for n, r in sorted(rutas.items()):
                datos = r.read_bytes()
                git = hashlib.sha1(b"blob %d\0" % len(datos) + datos).hexdigest()
                lista.append({"nombre": n, "bytes": len(datos), "git_sha": git})
            return {"marca": marca, "archivos": lista}
        if nombre not in rutas:
            raise HTTPException(status_code=404, detail=f"no existe {nombre!r}")
        return {"nombre": nombre, "b64": base64.b64encode(rutas[nombre].read_bytes()).decode()}

    @web.get("/salud")
    def salud() -> dict:
        return {"ok": True}

    return web
