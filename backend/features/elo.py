"""
Sistema ELO para equipos de fútbol
====================================
Calcula y actualiza ratings ELO por equipo, con ajustes por:
- Margen de victoria (goal difference)
- Importancia del partido (Mundial > Liga regular)
- Localía (home advantage)
- Competición (factores multiplicadores)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional


# ─────────────────────────────────────────────────────────────
# Constantes
# ─────────────────────────────────────────────────────────────

ELO_INICIAL = 1500.0
K_BASE = 20.0          # Factor K base (sensibilidad del modelo)
HOME_ADVANTAGE = 100.0  # Puntos de ventaja por localía

# Factores K multiplicadores por competición
K_MULTIPLICADORES = {
    "FIFA World Cup": 2.0,
    "UEFA Champions League": 1.5,
    "Copa America": 1.5,
    "international": 1.3,
    "Premier League": 1.2,
    "La Liga": 1.2,
    "Bundesliga": 1.2,
    "Serie A": 1.2,
    "Ligue 1": 1.1,
    "league": 1.0,
    "cup": 1.1,
    "friendly": 0.5,
}


@dataclass
class ResultadoELO:
    """Resultado de una actualización ELO."""
    team_id: int
    elo_antes: float
    elo_despues: float
    cambio: float
    probabilidad_esperada: float


@dataclass
class SistemaELO:
    """
    Sistema de ratings ELO para equipos de fútbol.

    Fórmula estándar FIFA-style:
      E_A = 1 / (1 + 10^((R_B - R_A) / 400))
      R_A_nuevo = R_A + K * W_A * (resultado - E_A)

    Donde W_A es el factor de margen de victoria.
    """

    ratings: dict[int, float] = field(default_factory=dict)
    k_base: float = K_BASE
    home_advantage: float = HOME_ADVANTAGE

    def get_rating(self, team_id: int) -> float:
        """Obtiene el ELO actual de un equipo (default: 1500)."""
        return self.ratings.get(team_id, ELO_INICIAL)

    def probabilidad_esperada(
        self,
        team_id_a: int,
        team_id_b: int,
        es_local_a: bool = False,
        es_neutral: bool = False,
    ) -> float:
        """
        Calcula la probabilidad esperada de victoria de A vs B.

        Args:
            team_id_a:  Equipo A
            team_id_b:  Equipo B
            es_local_a: Si A juega en casa
            es_neutral: Si el campo es neutral (ej: finales en sede neutral)

        Returns:
            Float [0, 1] — probabilidad de victoria del equipo A
        """
        r_a = self.get_rating(team_id_a)
        r_b = self.get_rating(team_id_b)

        # Ajuste por localía
        if not es_neutral:
            if es_local_a:
                r_a += self.home_advantage
            else:
                r_b += self.home_advantage

        return 1.0 / (1.0 + math.pow(10.0, (r_b - r_a) / 400.0))

    def factor_margen_victoria(self, goles_a: int, goles_b: int) -> float:
        """
        Factor de amplificación basado en el margen de victoria.
        Penaliza ligeramente las victorias amplias para estabilizar el sistema.

        Tabla de referencia:
          Empate:      1.0
          1 gol:       1.0
          2 goles:     1.5
          3+ goles:    1.75
        """
        diff = abs(goles_a - goles_b)
        if diff == 0 or diff == 1:
            return 1.0
        elif diff == 2:
            return 1.5
        else:
            return 1.75

    def actualizar(
        self,
        home_team_id: int,
        away_team_id: int,
        home_goals: int,
        away_goals: int,
        competition: str = "league",
        is_neutral: bool = False,
        match_importance: float = 1.0,
    ) -> tuple[ResultadoELO, ResultadoELO]:
        """
        Actualiza los ratings ELO tras un partido.

        Returns:
            Tuple (resultado_local, resultado_visitante)
        """
        r_home_antes = self.get_rating(home_team_id)
        r_away_antes = self.get_rating(away_team_id)

        # Probabilidad esperada antes del partido
        e_home = self.probabilidad_esperada(
            home_team_id, away_team_id,
            es_local_a=True, es_neutral=is_neutral
        )
        e_away = 1.0 - e_home

        # Resultado real (1 = victoria, 0.5 = empate, 0 = derrota)
        if home_goals > away_goals:
            s_home, s_away = 1.0, 0.0
        elif home_goals < away_goals:
            s_home, s_away = 0.0, 1.0
        else:
            s_home, s_away = 0.5, 0.5

        # Factor K ajustado
        k_mult = K_MULTIPLICADORES.get(competition, 1.0)
        k = self.k_base * k_mult * match_importance

        # Factor margen de victoria
        w = self.factor_margen_victoria(home_goals, away_goals)

        # Nuevos ratings
        r_home_nuevo = r_home_antes + k * w * (s_home - e_home)
        r_away_nuevo = r_away_antes + k * w * (s_away - e_away)

        self.ratings[home_team_id] = r_home_nuevo
        self.ratings[away_team_id] = r_away_nuevo

        return (
            ResultadoELO(
                team_id=home_team_id,
                elo_antes=r_home_antes,
                elo_despues=r_home_nuevo,
                cambio=r_home_nuevo - r_home_antes,
                probabilidad_esperada=e_home,
            ),
            ResultadoELO(
                team_id=away_team_id,
                elo_antes=r_away_antes,
                elo_despues=r_away_nuevo,
                cambio=r_away_nuevo - r_away_antes,
                probabilidad_esperada=e_away,
            ),
        )

    def diferencia_elo(self, team_a_id: int, team_b_id: int) -> float:
        """Diferencia de ELO: positivo = A es mejor."""
        return self.get_rating(team_a_id) - self.get_rating(team_b_id)

    def probabilidad_1x2_elo(
        self,
        home_team_id: int,
        away_team_id: int,
        is_neutral: bool = False,
        draw_factor: float = 0.20,
    ) -> dict[str, float]:
        """
        Estima probabilidades 1X2 usando solo ELO.
        No es el modelo final (ese usa XGBoost), pero sirve como feature.

        Args:
            draw_factor: Fracción del rango de probabilidades asignada a empate.

        Returns:
            {"home": float, "draw": float, "away": float}
        """
        p_home_raw = self.probabilidad_esperada(
            home_team_id, away_team_id,
            es_local_a=True, es_neutral=is_neutral
        )

        # Distribuir la probabilidad de empate proporcionalmente
        p_draw = draw_factor
        p_home = p_home_raw * (1 - draw_factor)
        p_away = (1 - p_home_raw) * (1 - draw_factor)

        # Normalizar
        total = p_home + p_draw + p_away
        return {
            "home": round(p_home / total, 4),
            "draw": round(p_draw / total, 4),
            "away": round(p_away / total, 4),
        }

    def get_ranking(self, top_n: Optional[int] = None) -> list[tuple[int, float]]:
        """
        Retorna el ranking de equipos por ELO descendente.

        Returns:
            Lista de (team_id, elo) ordenada de mayor a menor.
        """
        ranking = sorted(self.ratings.items(), key=lambda x: x[1], reverse=True)
        if top_n:
            return ranking[:top_n]
        return ranking


def construir_sistema_elo(partidos: list[dict], sistema: SistemaELO = None) -> SistemaELO:
    """
    Construye un SistemaELO a partir de una lista de partidos históricos
    ordenados cronológicamente.

    Args:
        partidos: Lista de dicts con keys:
                  home_team_id, away_team_id, home_goals, away_goals,
                  competition (str), is_neutral (bool), match_importance (float)
        sistema: Opcional. Un sistema ELO ya inicializado con ratings base.

    Returns:
        SistemaELO con ratings calculados.
    """
    if sistema is None:
        sistema = SistemaELO()
        
    for partido in partidos:
        sistema.actualizar(
            home_team_id=partido["home_team_id"],
            away_team_id=partido["away_team_id"],
            home_goals=partido["home_goals"],
            away_goals=partido["away_goals"],
            competition=partido.get("competition", "league"),
            is_neutral=partido.get("is_neutral", False),
            match_importance=partido.get("match_importance", 1.0),
        )
    return sistema
