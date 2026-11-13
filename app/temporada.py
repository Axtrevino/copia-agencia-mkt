"""Calendario de temporadas para el agente de ideas (México).

Fechas generales que mueven la conversación en México: feriados, puentes, días festivos de consumo
y temporadas de compras. Las fijas se calculan para cualquier año; las que cambian cada año (p. ej.
El Buen Fin) van en ESPECIALES con su fuente. Las fechas propias de la industria de cada marca
(temporadas de venta, ferias, cambios de ley) van en `marca.json` → `temporadas`:

    "temporadas": [
      {"inicio": "MM-DD", "fin": "MM-DD", "nombre": "…", "nota": "…"},          # cada año
      {"inicio": "AAAA-MM-DD", "fin": "AAAA-MM-DD", "nombre": "…", "fuente": "https://…"}
    ]

Con `"quincenas": true` en `marca.json` se agregan los días 15 y último de cada mes. Solo
librería estándar.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta


def pascua(anio: int) -> date:
    """Domingo de Pascua (algoritmo gregoriano anónimo)."""
    a, b, c = anio % 19, anio // 100, anio % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    m = (32 + 2 * e + 2 * i - h - k) % 7
    n = (a + 11 * h + 22 * m) // 451
    mes = (h + m - 7 * n + 114) // 31
    dia = (h + m - 7 * n + 114) % 31 + 1
    return date(anio, mes, dia)


def enesimo(anio: int, mes: int, dia_semana: int, n: int) -> date:
    """El n-ésimo día de la semana del mes (lunes=0); n=-1 es el último."""
    dias = [d for d in calendar.Calendar().itermonthdates(anio, mes) if d.month == mes]
    coinciden = [d for d in dias if d.weekday() == dia_semana]
    return coinciden[n if n < 0 else n - 1]


# Fechas generales que cambian cada año: (inicio, fin, nombre, nota, fuente). Agregar cada año.
ESPECIALES = [
    (
        date(2026, 11, 13),
        date(2026, 11, 17),
        "El Buen Fin",
        "Cinco días de ofertas en todo el país.",
        "https://www.xataka.com.mx/comercio-electronico/buen-fin-2026-confirma-fecha-mexico-este-ano-durara-seran-cinco-dias-ofertas/amp",
    ),
]


def _fijas(anio: int) -> list[tuple[date, date, str, str]]:
    p = pascua(anio)
    return [
        (date(anio, 1, 1), date(anio, 1, 6), "Año nuevo y Día de Reyes", "Rosca, propósitos."),
        (
            date(anio, 1, 2),
            date(anio, 1, 31),
            "Cuesta de enero",
            "Mes de gasto bajo después de diciembre.",
        ),
        (enesimo(anio, 2, 0, 1), enesimo(anio, 2, 0, 1), "Puente de la Constitución", ""),
        (date(anio, 2, 14), date(anio, 2, 14), "Día del amor y la amistad", ""),
        (enesimo(anio, 3, 0, 3), enesimo(anio, 3, 0, 3), "Puente de Benito Juárez", ""),
        (p - timedelta(days=7), p, "Semana Santa", "Vacaciones y viajes."),
        (date(anio, 4, 30), date(anio, 4, 30), "Día del Niño", ""),
        (date(anio, 5, 1), date(anio, 5, 1), "Día del Trabajo", "Descanso obligatorio."),
        (date(anio, 5, 10), date(anio, 5, 10), "Día de las Madres", "Gasto alto en regalos."),
        (date(anio, 5, 15), date(anio, 5, 15), "Día del Maestro", ""),
        (enesimo(anio, 6, 6, 3), enesimo(anio, 6, 6, 3), "Día del Padre", ""),
        (
            date(anio, 7, 15),
            date(anio, 8, 31),
            "Vacaciones de verano y regreso a clases",
            "Útiles, uniformes, inscripciones.",
        ),
        (date(anio, 9, 15), date(anio, 9, 16), "Fiestas patrias", "Noche mexicana; puente."),
        (
            date(anio, 11, 1),
            date(anio, 11, 2),
            "Día de Muertos",
            "Ofrendas, tradición, recordar a los que ya no están.",
        ),
        (enesimo(anio, 11, 0, 3), enesimo(anio, 11, 0, 3), "Puente de la Revolución", ""),
        (date(anio, 12, 12), date(anio, 12, 12), "Día de la Virgen de Guadalupe", ""),
        (date(anio, 12, 1), date(anio, 12, 23), "Posadas y cierre de año", ""),
        (date(anio, 12, 24), date(anio, 12, 25), "Nochebuena y Navidad", ""),
        (date(anio, 12, 31), date(anio, 12, 31), "Fin de año", ""),
    ]


def _quincenas(desde: date, hasta: date) -> list[dict]:
    salida = []
    d = desde
    while d <= hasta:
        ultimo = calendar.monthrange(d.year, d.month)[1]
        if d.day in (15, ultimo):
            salida.append({"inicio": d.isoformat(), "fin": d.isoformat(), "nombre": "Quincena"})
        d += timedelta(days=1)
    return salida


def _propias(desde: date, hasta: date, temporadas: list[dict]) -> list[dict]:
    """Las temporadas de `marca.json`: «MM-DD» se repite cada año; «AAAA-MM-DD» es una sola vez."""
    salida = []
    for t in temporadas or []:
        ini, fin = str(t.get("inicio") or ""), str(t.get("fin") or t.get("inicio") or "")
        try:
            if len(ini) == 5:
                fechas = [
                    (date.fromisoformat(f"{a}-{ini}"), date.fromisoformat(f"{a}-{fin}"))
                    for a in range(desde.year, hasta.year + 1)
                ]
            else:
                fechas = [(date.fromisoformat(ini), date.fromisoformat(fin))]
        except ValueError:
            continue
        for i, f in fechas:
            if i <= hasta and f >= desde:
                e = {"inicio": i.isoformat(), "fin": f.isoformat(), "nombre": str(t.get("nombre"))}
                for extra in ("nota", "fuente"):
                    if t.get(extra):
                        e[extra] = str(t[extra])
                salida.append(e)
    return salida


def eventos(
    desde: date, hasta: date, propias: list[dict] | None = None, quincenas: bool = False
) -> list[dict]:
    """Eventos que se cruzan con [desde, hasta], ordenados por fecha."""
    salida = []
    for anio in range(desde.year, hasta.year + 1):
        for inicio, fin, nombre, nota in _fijas(anio):
            if inicio <= hasta and fin >= desde:
                e = {"inicio": inicio.isoformat(), "fin": fin.isoformat(), "nombre": nombre}
                if nota:
                    e["nota"] = nota
                salida.append(e)
    for inicio, fin, nombre, nota, fuente in ESPECIALES:
        if inicio <= hasta and fin >= desde:
            salida.append(
                {
                    "inicio": inicio.isoformat(),
                    "fin": fin.isoformat(),
                    "nombre": nombre,
                    "nota": nota,
                    "fuente": fuente,
                }
            )
    salida += _propias(desde, hasta, propias or [])
    if quincenas:
        salida += _quincenas(desde, hasta)
    return sorted(salida, key=lambda e: (e["inicio"], e["nombre"]))


def alrededor(
    fecha: date,
    antes: int = 7,
    despues: int = 21,
    propias: list[dict] | None = None,
    quincenas: bool = False,
) -> list[dict]:
    """Lo que está pasando cerca de la fecha de un post (lo que viene pesa más)."""
    return eventos(
        fecha - timedelta(days=antes), fecha + timedelta(days=despues), propias, quincenas
    )
