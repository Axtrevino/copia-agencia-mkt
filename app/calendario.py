"""Días hábiles de México según el artículo 74 de la Ley Federal del Trabajo.

Solo librería estándar. Las fracciones I a VIII cubren: 1 de enero; primer lunes de febrero;
tercer lunes de marzo; 1 de mayo; 16 de septiembre; 1 de octubre cada seis años (transmisión del
Poder Ejecutivo Federal); tercer lunes de noviembre; 25 de diciembre. Si la agencia opera en otro
país, se reemplaza `es_feriado_mx` por el calendario de ese país.
"""

from __future__ import annotations

from datetime import date, timedelta


def _es_primer_lunes(fecha: date) -> bool:
    return fecha.weekday() == 0 and fecha.day <= 7


def _es_tercer_lunes(fecha: date) -> bool:
    return fecha.weekday() == 0 and 15 <= fecha.day <= 21


def es_feriado_mx(fecha: date) -> bool:
    """True si la fecha es día de descanso obligatorio (fracciones I a VIII del art. 74 LFT)."""
    if fecha.month == 1 and fecha.day == 1:
        return True
    if fecha.month == 2 and _es_primer_lunes(fecha):
        return True
    if fecha.month == 3 and _es_tercer_lunes(fecha):
        return True
    if fecha.month == 5 and fecha.day == 1:
        return True
    if fecha.month == 9 and fecha.day == 16:
        return True
    if fecha.month == 10 and fecha.day == 1:
        return fecha.year >= 2024 and (fecha.year - 2024) % 6 == 0
    if fecha.month == 11 and _es_tercer_lunes(fecha):
        return True
    return fecha.month == 12 and fecha.day == 25


def es_dia_habil_mx(fecha: date) -> bool:
    """True si es lunes a viernes y no es feriado obligatorio."""
    return fecha.weekday() < 5 and not es_feriado_mx(fecha)


def siguiente_dia_habil_mx(fecha: date) -> date:
    """Primer día hábil estrictamente posterior a la fecha dada."""
    candidato = fecha + timedelta(days=1)
    while not es_dia_habil_mx(candidato):
        candidato += timedelta(days=1)
    return candidato


def sumar_dias_habiles_mx(fecha: date, n: int) -> date:
    """Fecha que cae n días hábiles después de ``fecha`` (``fecha`` no cuenta)."""
    if n < 0:
        raise ValueError("El número de días hábiles no puede ser negativo")
    if n == 0:
        return fecha if es_dia_habil_mx(fecha) else siguiente_dia_habil_mx(fecha)
    candidato = fecha
    restantes = n
    while restantes > 0:
        candidato += timedelta(days=1)
        if es_dia_habil_mx(candidato):
            restantes -= 1
    return candidato


def dias_habiles_entre_mx(inicio: date, fin: date) -> int:
    """Días hábiles en el intervalo ``(inicio, fin]``. Devuelve 0 si ``fin <= inicio``."""
    if fin <= inicio:
        return 0
    dias = 0
    candidato = inicio
    while candidato < fin:
        candidato += timedelta(days=1)
        if es_dia_habil_mx(candidato):
            dias += 1
    return dias
