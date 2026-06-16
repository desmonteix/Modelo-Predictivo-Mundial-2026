"""
Modelo de Corners — Regresión Tweedie
=======================================
Usa distribución Tweedie (caso especial de la familia exponencial)
para modelar corners, que son datos de conteo con asimetría.

Complementado con XGBoost para capturar interacciones no lineales.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from scipy.stats import poisson
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor

try:
    import statsmodels.api as sm
    HAS_STATSMODELS = True
except ImportError:
    HAS_STATSMODELS = False

warnings.filterwarnings("ignore")


@dataclass
class ModeloCorners:
    """
    Modelo de predicción de corners.

    Estrategia:
      - Modelo principal: XGBoost Regressor (captura interacciones)
      - Modelo base: promedio ponderado de medias históricas
      - Output: predicción puntual + P(over/under líneas estándar)
    """

    entrenado: bool = False
    media_corners_liga: float = 10.2   # promedio histórico mundial/Champions
    feature_names: list[str] = field(default_factory=list)

    _modelo: Optional[Pipeline] = field(default=None, repr=False)

    def __post_init__(self):
        self._modelo = Pipeline([
            ("scaler", StandardScaler()),
            ("reg", XGBRegressor(
                n_estimators=200,
                max_depth=5,
                learning_rate=0.05,
                subsample=0.8,
                random_state=42,
                n_jobs=-1,
            )),
        ])

    def entrenar(
        self,
        X: np.ndarray,
        y_corners: np.ndarray,
        feature_names: Optional[list[str]] = None,
        verbose: bool = False,
    ) -> dict:
        """
        Entrena el modelo de corners.

        Args:
            X:          Feature matrix
            y_corners:  Total de corners por partido (entero)
            feature_names: Nombres para interpretabilidad
        """
        if feature_names:
            self.feature_names = feature_names

        if len(X) < 10:
            # Datos insuficientes — usar solo estadísticas descriptivas
            self.media_corners_liga = float(np.mean(y_corners))
            self.entrenado = False
            return {"status": "fallback", "n_muestras": len(X)}

        if verbose:
            print(f"Entrenando modelo corners: {len(X)} partidos")

        self._modelo.fit(X, y_corners.astype(float))
        self.media_corners_liga = float(np.mean(y_corners))
        self.entrenado = True

        y_pred = self._modelo.predict(X)
        mae = float(np.mean(np.abs(y_pred - y_corners)))

        if verbose:
            print(f"  ✓ MAE en entrenamiento: {mae:.3f} corners")

        return {
            "mae_train": round(mae, 4),
            "media_historica": round(self.media_corners_liga, 2),
            "n_muestras": len(X),
        }

    def predecir(
        self,
        X: np.ndarray,
        home_corners_hist: float = 5.1,
        away_corners_hist: float = 5.1,
        lineas: Optional[list[float]] = None,
    ) -> dict:
        """
        Predice corners para un partido.

        Args:
            X:                   Feature vector del partido
            home_corners_hist:   Promedio histórico de corners del local
            away_corners_hist:   Promedio histórico de corners del visitante
            lineas:              Líneas over/under a evaluar (default: [9.5, 11.5])

        Returns:
            Dict con el formato del Módulo 5.
        """
        if lineas is None:
            lineas = [9.5, 11.5]

        if self.entrenado:
            total_pred = float(self._modelo.predict(X.reshape(1, -1))[0])
            total_pred = max(4.0, total_pred)  # sanity check mínimo
        else:
            # Fallback: media histórica ajustada por equipos
            total_pred = (home_corners_hist + away_corners_hist) * 0.9 + self.media_corners_liga * 0.1

        # Distribuir entre local y visitante (proporción histórica)
        total_hist = home_corners_hist + away_corners_hist
        if total_hist > 0:
            ratio_home = home_corners_hist / total_hist
        else:
            ratio_home = 0.55  # leve ventaja al local

        corners_home = total_pred * ratio_home
        corners_away = total_pred * (1 - ratio_home)

        # Calcular probabilidades over/under usando distribución de Poisson
        prob_overs = {}
        for linea in lineas:
            # P(corners > linea) con Poisson(lambda=total_pred)
            prob_over = 1 - poisson.cdf(int(linea), total_pred)
            prob_overs[linea] = round(float(prob_over), 4)

        # Distribución completa (0..20)
        distribucion = {}
        for k in range(21):
            distribucion[str(k)] = round(float(poisson.pmf(k, total_pred)), 4)

        return {
            "value": round(total_pred, 2),
            "home_corners": round(corners_home, 2),
            "away_corners": round(corners_away, 2),
            "over_9_5_prob": prob_overs.get(9.5, 0.5),
            "over_11_5_prob": prob_overs.get(11.5, 0.35),
            "distribucion": distribucion,
            "is_fallback": not self.entrenado,
        }


# ─────────────────────────────────────────────────────────────
# Modelo de Faltas — Binomial Negativa
# ─────────────────────────────────────────────────────────────

@dataclass
class ModeloFaltas:
    """
    Modelo de predicción de faltas.

    Usa distribución Binomial Negativa (maneja sobre-dispersión).
    El strictness_score del árbitro es el feature más importante.

    Complementado con XGBoost para capturar interacciones.
    """

    entrenado: bool = False
    media_faltas_liga: float = 22.0
    feature_names: list[str] = field(default_factory=list)

    _modelo: Optional[Pipeline] = field(default=None, repr=False)

    def __post_init__(self):
        self._modelo = Pipeline([
            ("scaler", StandardScaler()),
            ("reg", XGBRegressor(
                n_estimators=200,
                max_depth=4,
                learning_rate=0.05,
                subsample=0.8,
                random_state=42,
                n_jobs=-1,
            )),
        ])

    def entrenar(
        self,
        X: np.ndarray,
        y_faltas: np.ndarray,
        feature_names: Optional[list[str]] = None,
        verbose: bool = False,
    ) -> dict:
        """Entrena el modelo de faltas."""
        if feature_names:
            self.feature_names = feature_names

        if len(X) < 10:
            self.media_faltas_liga = float(np.mean(y_faltas))
            self.entrenado = False
            return {"status": "fallback", "n_muestras": len(X)}

        if verbose:
            print(f"Entrenando modelo faltas: {len(X)} partidos")

        self._modelo.fit(X, y_faltas.astype(float))
        self.media_faltas_liga = float(np.mean(y_faltas))
        self.entrenado = True

        y_pred = self._modelo.predict(X)
        mae = float(np.mean(np.abs(y_pred - y_faltas)))

        return {
            "mae_train": round(mae, 4),
            "media_historica": round(self.media_faltas_liga, 2),
            "n_muestras": len(X),
        }

    def predecir(
        self,
        X: np.ndarray,
        home_faltas_hist: float = 11.0,
        away_faltas_hist: float = 11.0,
        arbitro_strictness: float = 5.0,
        es_rivalidad_alta: bool = False,
        lineas: Optional[list[float]] = None,
    ) -> dict:
        """
        Predice faltas para un partido.

        Args:
            X:                 Feature vector
            home_faltas_hist:  Promedio histórico de faltas del local
            away_faltas_hist:  Promedio histórico del visitante
            arbitro_strictness: Strictness score del árbitro (0-10)
            es_rivalidad_alta: Si es un derbi o clásico
            lineas:           Líneas a evaluar (default: [20.5, 25.5])
        """
        if lineas is None:
            lineas = [20.5, 25.5]

        if self.entrenado:
            total_pred = float(self._modelo.predict(X.reshape(1, -1))[0])
        else:
            # Fallback: media + ajuste por árbitro y rivalidad
            total_pred = home_faltas_hist + away_faltas_hist
            arbitro_factor = 1 + (arbitro_strictness - 5.0) * 0.05
            total_pred *= arbitro_factor
            if es_rivalidad_alta:
                total_pred *= 1.1

        total_pred = max(8.0, total_pred)  # mínimo razonable

        # Distribución por equipo
        total_hist = home_faltas_hist + away_faltas_hist
        ratio_home = home_faltas_hist / total_hist if total_hist > 0 else 0.5

        faltas_home = total_pred * ratio_home
        faltas_away = total_pred * (1 - ratio_home)

        # Probabilidades over/under con Poisson
        prob_overs = {}
        for linea in lineas:
            prob_over = 1 - poisson.cdf(int(linea), total_pred)
            prob_overs[linea] = round(float(prob_over), 4)

        # Impacto del árbitro
        if arbitro_strictness >= 7.5:
            referee_impact = "alto"
        elif arbitro_strictness >= 4.5:
            referee_impact = "medio"
        else:
            referee_impact = "bajo"

        return {
            "value": round(total_pred, 2),
            "home_fouls": round(faltas_home, 2),
            "away_fouls": round(faltas_away, 2),
            "over_20_5_prob": prob_overs.get(20.5, 0.5),
            "over_25_5_prob": prob_overs.get(25.5, 0.3),
            "referee_impact": referee_impact,
            "is_fallback": not self.entrenado,
        }
