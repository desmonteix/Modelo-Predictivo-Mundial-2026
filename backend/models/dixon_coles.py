"""
Modelo Dixon-Coles — Predicción de Goles
==========================================
Implementa el modelo Dixon-Coles (1997): extensión de Poisson bivariada
con corrección de dependencia para resultados de baja puntuación (0-0, 1-0, 0-1, 1-1).

Referencia: Dixon, M.J. & Coles, S.G. (1997). Modelling Association Football Scores
            and Inefficiencies in the Football Betting Market.

El modelo asigna a cada equipo:
  - α_i (ataque): fuerza ofensiva
  - β_i (defensa): fortaleza defensiva
  - λ (home advantage): ventaja del local

Goles local   ~ Poisson(λ_home)   donde λ_home = α_home * β_away * γ_home_adv
Goles visitante ~ Poisson(λ_away) donde λ_away = α_away * β_home
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from scipy.optimize import minimize
from scipy.stats import poisson

warnings.filterwarnings("ignore", category=RuntimeWarning)


# ─────────────────────────────────────────────────────────────
# Factor de corrección Dixon-Coles
# ─────────────────────────────────────────────────────────────

def correccion_dixon_coles(
    goles_home: int,
    goles_away: int,
    lambda_home: float,
    lambda_away: float,
    rho: float,
) -> float:
    """
    Factor de corrección τ(x, y, λ, μ, ρ) del modelo Dixon-Coles.
    Ajusta la dependencia entre los goles de ambos equipos para
    resultados de baja puntuación.

    ρ es el parámetro de correlación (negativo en fútbol: cuando uno marca más,
    el otro tiende a marcar menos).
    """
    if goles_home == 0 and goles_away == 0:
        return 1 - lambda_home * lambda_away * rho
    elif goles_home == 0 and goles_away == 1:
        return 1 + lambda_home * rho
    elif goles_home == 1 and goles_away == 0:
        return 1 + lambda_away * rho
    elif goles_home == 1 and goles_away == 1:
        return 1 - rho
    else:
        return 1.0


# ─────────────────────────────────────────────────────────────
# Modelo Dixon-Coles
# ─────────────────────────────────────────────────────────────

@dataclass
class ModeloDixonColes:
    """
    Modelo Dixon-Coles para predicción de goles.

    Atributos (aprendidos en el ajuste):
        alpha: Parámetros de ataque por equipo {team_id: valor}
        beta:  Parámetros de defensa por equipo {team_id: valor}
        gamma: Ventaja de jugar en casa (multiplicador)
        rho:   Parámetro de corrección para bajas puntuaciones
    """

    alpha: dict[int, float] = field(default_factory=dict)  # ataque
    beta: dict[int, float] = field(default_factory=dict)   # defensa
    gamma: float = 1.35    # home advantage típico en fútbol
    rho: float = -0.13     # correlación Dixon-Coles típica
    equipos: list[int] = field(default_factory=list)
    entrenado: bool = False

    def lambda_esperada(
        self,
        team_ataque_id: int,
        team_defensa_id: int,
        es_local: bool,
    ) -> float:
        """
        Calcula el λ (goles esperados) de un equipo contra otro.

        Args:
            team_ataque_id:  Equipo que ataca
            team_defensa_id: Equipo que defiende
            es_local:        Si el atacante juega en casa

        Returns:
            λ > 0 (goles esperados de Poisson)
        """
        alpha_i = self.alpha.get(team_ataque_id, 1.0)
        beta_j = self.beta.get(team_defensa_id, 1.0)
        home_mult = self.gamma if es_local else 1.0
        return alpha_i * beta_j * home_mult

    def _log_verosimilitud(self, params: np.ndarray, datos: list[dict]) -> float:
        """
        Función de log-verosimilitud negativa para optimización.

        Args:
            params: Vector [alpha_1,...,alpha_n, beta_1,...,beta_n, gamma, rho]
            datos:  Lista de partidos {home_id, away_id, home_goals, away_goals, weight}

        Returns:
            -log-likelihood (minimizar)
        """
        n = len(self.equipos)
        idx = {equipo: i for i, equipo in enumerate(self.equipos)}

        alphas = np.exp(params[:n])
        betas = np.exp(params[n:2*n])
        gamma = np.exp(params[2*n])
        rho = params[2*n + 1]

        # Restringir rho al rango (-1, 0]
        rho = max(-0.99, min(0.0, rho))

        log_l = 0.0
        for partido in datos:
            i = idx.get(partido["home_id"])
            j = idx.get(partido["away_id"])
            if i is None or j is None:
                continue

            lmb_home = alphas[i] * betas[j] * gamma
            lmb_away = alphas[j] * betas[i]

            g_home = partido["home_goals"]
            g_away = partido["away_goals"]
            peso = partido.get("weight", 1.0)

            if lmb_home <= 0 or lmb_away <= 0:
                continue

            tau = correccion_dixon_coles(g_home, g_away, lmb_home, lmb_away, rho)
            if tau <= 0:
                continue

            contrib = (
                np.log(tau)
                + g_home * np.log(lmb_home) - lmb_home
                + g_away * np.log(lmb_away) - lmb_away
            )
            log_l += peso * contrib

        return -log_l

    def entrenar(
        self,
        datos: list[dict],
        max_iter: int = 500,
        verbose: bool = False,
    ) -> dict:
        """
        Ajusta los parámetros del modelo por máxima verosimilitud ponderada.

        Args:
            datos: Lista de partidos con keys:
                   home_id (int), away_id (int),
                   home_goals (int), away_goals (int),
                   weight (float, default 1.0)

        Returns:
            Dict con métricas del ajuste: log-likelihood, convergencia, etc.
        """
        # Extraer todos los equipos del dataset
        equipos_set: set[int] = set()
        for p in datos:
            equipos_set.add(p["home_id"])
            equipos_set.add(p["away_id"])

        self.equipos = sorted(list(equipos_set))
        n = len(self.equipos)

        if verbose:
            print(f"Entrenando Dixon-Coles con {len(datos)} partidos y {n} equipos...")

        # Parámetros iniciales (todos en 0 en escala log)
        x0 = np.zeros(2 * n + 2)
        x0[2*n] = np.log(self.gamma)   # gamma inicial
        x0[2*n + 1] = self.rho          # rho inicial

        resultado = minimize(
            self._log_verosimilitud,
            x0,
            args=(datos,),
            method="L-BFGS-B",
            options={"maxiter": max_iter, "ftol": 1e-10},
        )

        # Extraer parámetros
        params = resultado.x
        alphas = np.exp(params[:n])
        betas = np.exp(params[n:2*n])

        for i, equipo_id in enumerate(self.equipos):
            self.alpha[equipo_id] = float(alphas[i])
            self.beta[equipo_id] = float(betas[i])

        self.gamma = float(np.exp(params[2*n]))
        self.rho = float(max(-0.99, min(0.0, params[2*n + 1])))
        self.entrenado = True

        return {
            "convergido": resultado.success,
            "log_likelihood": -resultado.fun,
            "iteraciones": resultado.nit,
            "n_equipos": n,
            "n_partidos": len(datos),
            "gamma": round(self.gamma, 4),
            "rho": round(self.rho, 4),
        }

    def predecir_distribucion(
        self,
        home_team_id: int,
        away_team_id: int,
        max_goles: int = 10,
        es_neutral: bool = False,
        home_modifier: float = 1.0,
        away_modifier: float = 1.0,
    ) -> dict:
        """
        Genera la distribución de probabilidad conjunta P(home=i, away=j).

        Args:
            home_team_id: ID del equipo local
            away_team_id: ID del equipo visitante
            max_goles:    Máximo número de goles a considerar (default 10)
            es_neutral:   Si el campo es neutral (sin ventaja de localía)

        Returns:
            Dict con:
              - matrix: np.array (max_goles+1, max_goles+1)
              - lambda_home: float
              - lambda_away: float
              - rho: float
        """
        # Para campo neutral, ignorar el multiplicador de localía
        es_local = not es_neutral

        lmb_home = self.lambda_esperada(home_team_id, away_team_id, es_local=es_local) * home_modifier
        lmb_away = self.lambda_esperada(away_team_id, home_team_id, es_local=False) * away_modifier

        # Usar valores promedio si el equipo no está en el modelo
        if home_team_id not in self.alpha:
            lmb_home = 1.3 * (self.gamma if es_local else 1.0)
        if away_team_id not in self.alpha:
            lmb_away = 1.0

        matrix = np.zeros((max_goles + 1, max_goles + 1))

        for i in range(max_goles + 1):
            for j in range(max_goles + 1):
                p_base = (
                    poisson.pmf(i, lmb_home)
                    * poisson.pmf(j, lmb_away)
                )
                tau = correccion_dixon_coles(i, j, lmb_home, lmb_away, self.rho)
                matrix[i, j] = p_base * tau

        # Normalizar para que sume 1.0
        total = matrix.sum()
        if total > 0:
            matrix /= total

        return {
            "matrix": matrix,
            "lambda_home": round(lmb_home, 4),
            "lambda_away": round(lmb_away, 4),
            "rho": round(self.rho, 4),
        }

    def predecir(
        self,
        home_team_id: int,
        away_team_id: int,
        es_neutral: bool = False,
        max_goles: int = 10,
        home_modifier: float = 1.0,
        away_modifier: float = 1.0,
    ) -> dict:
        """
        Genera predicción completa para un partido.

        Returns:
            Dict con el formato del Módulo 5:
            - goals_home: distribución y valor esperado
            - goals_away: distribución y valor esperado
            - total_goals: distribución conjunta
            - result_1x2: probabilidades 1/X/2
        """
        resultado = self.predecir_distribucion(
            home_team_id, away_team_id, max_goles, es_neutral, home_modifier, away_modifier
        )
        matrix = resultado["matrix"]
        lmb_home = resultado["lambda_home"]
        lmb_away = resultado["lambda_away"]

        # ── Distribución de goles local ───────────────────────
        dist_home = matrix.sum(axis=1)  # suma sobre columnas (away)
        dist_away = matrix.sum(axis=0)  # suma sobre filas (home)

        goles_home_dist = {
            "0": round(float(dist_home[0]), 4),
            "1": round(float(dist_home[1]), 4),
            "2": round(float(dist_home[2]), 4),
            "3+": round(float(dist_home[3:].sum()), 4),
        }
        goles_away_dist = {
            "0": round(float(dist_away[0]), 4),
            "1": round(float(dist_away[1]), 4),
            "2": round(float(dist_away[2]), 4),
            "3+": round(float(dist_away[3:].sum()), 4),
        }

        # ── Valor esperado y moda ─────────────────────────────
        goles_values = np.arange(max_goles + 1)
        e_home = float(np.dot(goles_values, dist_home))
        e_away = float(np.dot(goles_values, dist_away))
        moda_home = int(np.argmax(dist_home))
        moda_away = int(np.argmax(dist_away))

        # ── Goles totales ─────────────────────────────────────
        total_goles = e_home + e_away
        # Distribución de goles totales
        dist_total = {}
        for t in range(max_goles * 2 + 1):
            p = 0.0
            for i in range(min(t + 1, max_goles + 1)):
                j = t - i
                if j <= max_goles:
                    p += matrix[i, j]
            dist_total[t] = round(p, 4)

        over_2_5 = sum(v for k, v in dist_total.items() if k > 2.5)
        under_2_5 = 1.0 - over_2_5

        # ── Resultado 1X2 ─────────────────────────────────────
        p_home_win = float(np.sum(np.tril(matrix, k=-1)))  # home > away
        p_draw = float(np.sum(np.diag(matrix)))             # home == away
        p_away_win = float(np.sum(np.triu(matrix, k=1)))   # away > home

        # Normalizar
        total_12x = p_home_win + p_draw + p_away_win
        if total_12x > 0:
            p_home_win /= total_12x
            p_draw /= total_12x
            p_away_win /= total_12x

        if p_home_win >= p_draw and p_home_win >= p_away_win:
            predicted_result = "H"
        elif p_draw >= p_home_win and p_draw >= p_away_win:
            predicted_result = "D"
        else:
            predicted_result = "A"

        # ── Exact Scores ─────────────────────────────────────
        exact_scores = []
        for i in range(min(max_goles, 6)):
            for j in range(min(max_goles, 6)):
                prob = float(matrix[i, j])
                if prob > 0.005:
                    exact_scores.append({"home": i, "away": j, "prob": round(prob, 4)})
        exact_scores.sort(key=lambda x: x["prob"], reverse=True)
        exact_scores = exact_scores[:6]

        return {
            "lambda_home": lmb_home,
            "lambda_away": lmb_away,
            "goals_home": {
                "value": round(e_home, 2),
                "most_likely": moda_home,
                "distribution": goles_home_dist,
            },
            "goals_away": {
                "value": round(e_away, 2),
                "most_likely": moda_away,
                "distribution": goles_away_dist,
            },
            "total_goals": {
                "value": round(total_goles, 2),
                "over_2_5_prob": round(over_2_5, 4),
                "under_2_5_prob": round(under_2_5, 4),
                "most_likely_range": self._rango_mas_probable(dist_total),
            },
            "result_1x2_dixon": {
                "home_win_prob": round(p_home_win, 4),
                "draw_prob": round(p_draw, 4),
                "away_win_prob": round(p_away_win, 4),
                "predicted_result": predicted_result,
            },
            "exact_scores": exact_scores,
        }

    def _rango_mas_probable(self, dist_total: dict[int, float]) -> str:
        """Determina el rango de goles totales más probable."""
        max_prob = 0.0
        max_rango = "2-3"
        rangos = [(0, 1, "0-1"), (2, 3, "2-3"), (4, 5, "4-5"), (6, 99, "6+")]
        for lo, hi, label in rangos:
            prob = sum(v for k, v in dist_total.items() if lo <= k <= hi)
            if prob > max_prob:
                max_prob = prob
                max_rango = label
        return max_rango

    def tiene_parametros(self, team_id: int) -> bool:
        """Verifica si el modelo tiene parámetros para un equipo."""
        return team_id in self.alpha

    def fallback_poisson(
        self,
        avg_goals_home: float = 1.5,
        avg_goals_away: float = 1.0,
        max_goles: int = 8,
    ) -> dict:
        """
        Modelo de respaldo: Poisson simple sin parámetros de equipo.
        Se usa cuando los datos son insuficientes.
        """
        goles_values = np.arange(max_goles + 1)
        dist_home = np.array([poisson.pmf(k, avg_goals_home) for k in goles_values])
        dist_away = np.array([poisson.pmf(k, avg_goals_away) for k in goles_values])

        # Normalizar
        dist_home /= dist_home.sum()
        dist_away /= dist_away.sum()

        total = avg_goals_home + avg_goals_away
        
        exact_scores = []
        for i in range(min(max_goles, 6)):
            for j in range(min(max_goles, 6)):
                prob = float(dist_home[i] * dist_away[j])
                if prob > 0.005:
                    exact_scores.append({"home": i, "away": j, "prob": round(prob, 4)})
        exact_scores.sort(key=lambda x: x["prob"], reverse=True)
        exact_scores = exact_scores[:6]
        
        return {
            "lambda_home": avg_goals_home,
            "lambda_away": avg_goals_away,
            "goals_home": {
                "value": avg_goals_home,
                "most_likely": int(np.argmax(dist_home)),
                "distribution": {
                    "0": round(float(dist_home[0]), 4),
                    "1": round(float(dist_home[1]), 4),
                    "2": round(float(dist_home[2]), 4),
                    "3+": round(float(dist_home[3:].sum()), 4),
                },
            },
            "goals_away": {
                "value": avg_goals_away,
                "most_likely": int(np.argmax(dist_away)),
                "distribution": {
                    "0": round(float(dist_away[0]), 4),
                    "1": round(float(dist_away[1]), 4),
                    "2": round(float(dist_away[2]), 4),
                    "3+": round(float(dist_away[3:].sum()), 4),
                },
            },
            "total_goals": {
                "value": round(total, 2),
                "over_2_5_prob": round(1 - poisson.cdf(2, total), 4),
                "under_2_5_prob": round(poisson.cdf(2, total), 4),
                "most_likely_range": "2-3",
            },
            "result_1x2_dixon": {
                "home_win_prob": round(float(sum(dist_home[i] * dist_away[j] for i in range(max_goles+1) for j in range(i))), 4),
                "draw_prob": round(float(sum(dist_home[k] * dist_away[k] for k in range(max_goles+1))), 4),
                "away_win_prob": round(float(sum(dist_home[i] * dist_away[j] for i in range(max_goles+1) for j in range(i+1, max_goles+1))), 4),
                "predicted_result": "H" if avg_goals_home >= avg_goals_away + 0.5 else ("D" if abs(avg_goals_home - avg_goals_away) < 0.5 else "A"),
            },
            "exact_scores": exact_scores,
            "is_fallback": True,
        }
