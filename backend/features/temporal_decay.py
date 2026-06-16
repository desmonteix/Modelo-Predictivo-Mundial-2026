"""
Módulo 6 — Sistema de Ponderación Temporal
==========================================
Implementa la función de decay exponencial y los breakpoints duros
para calcular el peso de cada partido histórico.

Función:  w(t) = e^(-λ · semanas_desde_partido)
λ default = 0.02  →  vida media ≈ 35 semanas ≈ 1 temporada

Tabla de pesos:
  4  semanas → 0.923  (casi completo)
  26 semanas → 0.607  (relevante)
  52 semanas → 0.310  (contexto)
 104 semanas → 0.096  (uso marginal)
 150 semanas → <0.05  → DESCARTAR
"""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Optional
import os

# ─────────────────────────────────────────────────────────────
# Parámetros configurables por variables de entorno
# ─────────────────────────────────────────────────────────────
LAMBDA_DECAY: float = float(os.getenv("LAMBDA_DECAY", "0.02"))
PESO_MINIMO: float = float(os.getenv("PESO_MINIMO", "0.05"))


def calcular_peso(
    fecha_partido: date | datetime,
    fecha_referencia: Optional[date | datetime] = None,
    lambda_decay: float = LAMBDA_DECAY,
    peso_minimo: float = PESO_MINIMO,
) -> float:
    """
    Calcula el peso temporal de un partido dado su fecha.

    Args:
        fecha_partido:    Fecha del partido histórico.
        fecha_referencia: Fecha desde la que calcular (default: hoy).
        lambda_decay:     Velocidad de decay (default: 0.02).
        peso_minimo:      Threshold de descarte (default: 0.05).

    Returns:
        Float en [0, 1]. Si < peso_minimo, el dato debe descartarse.
    """
    if fecha_referencia is None:
        fecha_referencia = date.today()

    # Normalizar a date si viene como datetime
    if isinstance(fecha_partido, datetime):
        fecha_partido = fecha_partido.date()
    if isinstance(fecha_referencia, datetime):
        fecha_referencia = fecha_referencia.date()

    delta_dias = (fecha_referencia - fecha_partido).days
    delta_semanas = max(0.0, delta_dias / 7.0)

    peso = math.exp(-lambda_decay * delta_semanas)
    return peso


def debe_descartar(
    fecha_partido: date | datetime,
    fecha_referencia: Optional[date | datetime] = None,
    lambda_decay: float = LAMBDA_DECAY,
    peso_minimo: float = PESO_MINIMO,
) -> bool:
    """
    Retorna True si el dato debe ignorarse por peso < peso_minimo.
    """
    peso = calcular_peso(fecha_partido, fecha_referencia, lambda_decay, peso_minimo)
    return peso < peso_minimo


def calcular_pesos_lista(
    fechas: list[date | datetime],
    fecha_referencia: Optional[date | datetime] = None,
    lambda_decay: float = LAMBDA_DECAY,
    peso_minimo: float = PESO_MINIMO,
    filtrar_descartados: bool = True,
) -> list[tuple[date, float]]:
    """
    Calcula pesos para una lista de fechas.

    Returns:
        Lista de (fecha, peso) ordenada por fecha descendente.
        Si filtrar_descartados=True, excluye entradas con peso < peso_minimo.
    """
    resultado = []
    for fecha in fechas:
        peso = calcular_peso(fecha, fecha_referencia, lambda_decay, peso_minimo)
        if not filtrar_descartados or peso >= peso_minimo:
            f = fecha.date() if isinstance(fecha, datetime) else fecha
            resultado.append((f, peso))

    return sorted(resultado, key=lambda x: x[0], reverse=True)


# ─────────────────────────────────────────────────────────────
# Breakpoints duros
# ─────────────────────────────────────────────────────────────

class BreakpointManager:
    """
    Gestiona los breakpoints duros que resetean el historial táctico
    de un equipo (cambio de entrenador, ascenso/descenso, etc.)
    """

    def __init__(self, coach_changes: list[dict], team_id: int):
        """
        Args:
            coach_changes: Lista de dicts con {date, team_id, old_coach, new_coach}
            team_id: ID del equipo a evaluar
        """
        self.team_id = team_id
        self.breakpoints: list[date] = sorted([
            c["date"] if isinstance(c["date"], date) else c["date"].date()
            for c in coach_changes
            if c.get("team_id") == team_id
        ])

    def get_peso_ajustado(
        self,
        fecha_partido: date | datetime,
        fecha_referencia: Optional[date | datetime] = None,
        lambda_decay: float = LAMBDA_DECAY,
        peso_minimo: float = PESO_MINIMO,
    ) -> float:
        """
        Calcula el peso aplicando la política de breakpoints:
        - Si el partido ocurrió ANTES del último cambio de entrenador → peso = 0
          (los datos tácticos anteriores no son relevantes)
        - En otros casos, devuelve el peso exponencial normal.
        """
        if fecha_referencia is None:
            fecha_referencia = date.today()

        f_partido = fecha_partido.date() if isinstance(fecha_partido, datetime) else fecha_partido
        f_ref = fecha_referencia.date() if isinstance(fecha_referencia, datetime) else fecha_referencia

        # Buscar el último breakpoint antes de la fecha de referencia
        breakpoints_pasados = [bp for bp in self.breakpoints if bp <= f_ref]

        if breakpoints_pasados:
            ultimo_breakpoint = max(breakpoints_pasados)
            if f_partido < ultimo_breakpoint:
                # El partido es anterior al cambio de entrenador → peso 0
                return 0.0

        return calcular_peso(fecha_partido, fecha_referencia, lambda_decay, peso_minimo)


# ─────────────────────────────────────────────────────────────
# Excepciones — datos que NO se descartan aunque sean antiguos
# ─────────────────────────────────────────────────────────────

EXCEPCIONES_HISTORICAS = {
    "FIFA World Cup Final",
    "UEFA Champions League Final",
    "Copa America Final",
    "Copa del Mundo Final",
}


def es_excepcion_historica(match_stage: Optional[str]) -> bool:
    """
    Finales de grandes competiciones mantienen valor contextual
    aunque superen el umbral de descarte temporal.
    """
    if not match_stage:
        return False
    return any(exc.lower() in match_stage.lower() for exc in EXCEPCIONES_HISTORICAS)


def calcular_peso_partido(
    fecha_partido: date | datetime,
    match_stage: Optional[str] = None,
    fecha_referencia: Optional[date | datetime] = None,
    lambda_decay: float = LAMBDA_DECAY,
    peso_minimo: float = PESO_MINIMO,
    breakpoint_manager: Optional[BreakpointManager] = None,
) -> float:
    """
    Función principal de cálculo de peso de un partido.
    Integra decay exponencial, breakpoints y excepciones históricas.

    Returns:
        Float en [0, 1]. Si < peso_minimo (y no es excepción), el dato se descarta.
    """
    # Las finales históricas siempre se mantienen con peso mínimo de 0.1
    if es_excepcion_historica(match_stage):
        peso_base = calcular_peso(fecha_partido, fecha_referencia, lambda_decay, peso_minimo)
        return max(peso_base, 0.10)

    # Aplicar breakpoints si existe manager
    if breakpoint_manager:
        return breakpoint_manager.get_peso_ajustado(
            fecha_partido, fecha_referencia, lambda_decay, peso_minimo
        )

    return calcular_peso(fecha_partido, fecha_referencia, lambda_decay, peso_minimo)


# ─────────────────────────────────────────────────────────────
# Utilidades de debug / reporting
# ─────────────────────────────────────────────────────────────

def tabla_pesos_ejemplo(lambda_decay: float = LAMBDA_DECAY) -> list[dict]:
    """
    Genera una tabla de pesos de ejemplo para distintas antigüedades.
    Útil para visualización en el dashboard.
    """
    casos = [
        ("4 semanas", 4),
        ("6 meses", 26),
        ("1 temporada", 52),
        ("2 temporadas", 104),
        ("3+ temporadas", 156),
    ]
    resultado = []
    for label, semanas in casos:
        peso = math.exp(-lambda_decay * semanas)
        resultado.append({
            "antiguedad": label,
            "semanas": semanas,
            "peso": round(peso, 4),
            "descartado": peso < PESO_MINIMO,
        })
    return resultado
