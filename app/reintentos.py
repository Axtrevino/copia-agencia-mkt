"""Reintentos con espera exponencial para llamadas a APIs externas que fallan de vez en cuando.

Librería estándar, sin dependencias. `dormir` se inyecta para que las pruebas no esperen de verdad.
"""

from __future__ import annotations

import time
from collections.abc import Callable


def con_reintentos[T](
    fn: Callable[[], T],
    intentos: int = 3,
    espera_inicial: float = 1.0,
    factor: float = 2.0,
    reintentar_si: tuple[type[BaseException], ...] = (Exception,),
    dormir: Callable[[float], None] = time.sleep,
) -> T:
    """Llama a `fn` y reintenta si lanza una excepción de `reintentar_si`.

    Entre intentos espera `espera_inicial`, luego `espera_inicial * factor`, etc. (1 s, 2 s, 4 s…).
    Devuelve el resultado del primer intento exitoso; si se agotan los intentos, vuelve a lanzar la
    última excepción. Una excepción fuera de `reintentar_si` se propaga de inmediato.
    """
    if intentos < 1:
        raise ValueError(f"intentos debe ser al menos 1, recibí {intentos}")

    espera = espera_inicial
    for intento in range(intentos):
        try:
            return fn()
        except reintentar_si:
            if intento == intentos - 1:
                raise
            dormir(espera)
            espera *= factor
