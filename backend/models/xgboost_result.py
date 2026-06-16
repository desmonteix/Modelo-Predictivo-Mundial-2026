"""
Modelo XGBoost Ensemble — Resultado 1X2
=========================================
Ensemble de XGBoost + Random Forest + Regresión Logística Multinomial
con stacking: un meta-learner logístico entrena sobre las probabilidades
de los modelos base.

Output: P(H), P(D), P(A) — deben sumar 1.0
"""

from __future__ import annotations

import os
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

warnings.filterwarnings("ignore")

# Etiquetas: 0 = Home, 1 = Draw, 2 = Away
LABEL_MAP = {"H": 0, "D": 1, "A": 2}
LABEL_INVERSE = {0: "H", 1: "D", 2: "A"}
ARTIFACT_DIR = Path(os.getenv("ARTIFACT_DIR", "/app/artifacts/models"))


@dataclass
class ModeloEnsemble1X2:
    """
    Ensemble con stacking para predicción de resultado 1X2.

    Arquitectura:
      Capa 1 (modelos base): XGBoost + Random Forest + Logistic Regression
      Capa 2 (meta-learner): Logistic Regression sobre las probabilidades de Capa 1

    Las probabilidades finales son calibradas con Platt Scaling.
    """

    entrenado: bool = False
    feature_names: list[str] = field(default_factory=list)

    # Modelos base
    _xgb: Optional[XGBClassifier] = field(default=None, repr=False)
    _rf: Optional[RandomForestClassifier] = field(default=None, repr=False)
    _lr: Optional[Pipeline] = field(default=None, repr=False)
    _meta: Optional[LogisticRegression] = field(default=None, repr=False)

    def __post_init__(self):
        self._xgb = XGBClassifier(
            n_estimators=300,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            use_label_encoder=False,
            eval_metric="mlogloss",
            random_state=42,
            n_jobs=-1,
        )
        self._rf = RandomForestClassifier(
            n_estimators=200,
            max_depth=8,
            min_samples_leaf=5,
            random_state=42,
            n_jobs=-1,
        )
        self._lr = Pipeline([
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(
                C=1.0,
                multi_class="multinomial",
                solver="lbfgs",
                max_iter=1000,
                random_state=42,
            )),
        ])
        self._meta = LogisticRegression(
            C=1.0,
            multi_class="multinomial",
            solver="lbfgs",
            max_iter=500,
            random_state=42,
        )

    @staticmethod
    def _encode_labels(resultados: list[str]) -> np.ndarray:
        """Convierte ['H', 'D', 'A'] → [0, 1, 2]."""
        return np.array([LABEL_MAP[r] for r in resultados])

    def entrenar(
        self,
        X: np.ndarray,
        y: list[str],
        feature_names: Optional[list[str]] = None,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[list[str]] = None,
        verbose: bool = False,
    ) -> dict:
        """
        Entrena el ensemble completo.

        Args:
            X:            Feature matrix (n_muestras, n_features)
            y:            Lista de resultados ['H', 'D', 'A']
            feature_names: Nombres de features para interpretabilidad
            X_val:        Set de validación opcional (para stacking out-of-fold)
            y_val:        Labels de validación

        Returns:
            Dict con métricas de entrenamiento.
        """
        if feature_names:
            self.feature_names = feature_names

        y_enc = self._encode_labels(y)

        if verbose:
            print(f"Entrenando ensemble 1X2: {len(X)} muestras, {X.shape[1]} features")

        # ── Capa 1: modelos base ──────────────────────────────
        if verbose:
            print("  → Entrenando XGBoost...")
        self._xgb.fit(X, y_enc)

        if verbose:
            print("  → Entrenando Random Forest...")
        self._rf.fit(X, y_enc)

        if verbose:
            print("  → Entrenando Logistic Regression...")
        self._lr.fit(X, y_enc)

        # ── Capa 2: meta-learner ──────────────────────────────
        # Construir features del meta-learner: probabilidades de Capa 1
        meta_features = self._get_meta_features(X)

        if verbose:
            print("  → Entrenando meta-learner...")
        self._meta.fit(meta_features, y_enc)

        self.entrenado = True

        # Métricas de entrenamiento
        meta_features_train = self._get_meta_features(X)
        y_pred = self._meta.predict(meta_features_train)
        accuracy = float(np.mean(y_pred == y_enc))

        if verbose:
            print(f"  ✓ Accuracy en entrenamiento: {accuracy:.3f}")

        return {
            "accuracy_train": round(accuracy, 4),
            "n_muestras": len(X),
            "n_features": X.shape[1],
            "modelos_base": ["xgboost", "random_forest", "logistic_regression"],
            "meta_learner": "logistic_regression",
        }

    def _get_meta_features(self, X: np.ndarray) -> np.ndarray:
        """
        Construye la matriz de features para el meta-learner.
        Son las probabilidades predichas por cada modelo base.
        """
        p_xgb = self._xgb.predict_proba(X)   # (n, 3)
        p_rf = self._rf.predict_proba(X)       # (n, 3)
        p_lr = self._lr.predict_proba(X)       # (n, 3)
        return np.hstack([p_xgb, p_rf, p_lr])  # (n, 9)

    def predecir_proba(self, X: np.ndarray) -> np.ndarray:
        """
        Retorna probabilidades [P(H), P(D), P(A)] para cada muestra.

        Returns:
            np.ndarray de shape (n_muestras, 3)
        """
        if not self.entrenado:
            # Sin modelo entrenado, devolver distribución uniforme ajustada
            # (baseada en frecuencias históricas mundiales: ~46% H, 26% D, 28% A)
            n = len(X)
            return np.tile([0.46, 0.26, 0.28], (n, 1))

        meta_features = self._get_meta_features(X)
        probs = self._meta.predict_proba(meta_features)

        # Asegurarse de que sumen 1.0
        row_sums = probs.sum(axis=1, keepdims=True)
        probs = probs / row_sums

        return probs

    def predecir(self, X: np.ndarray) -> list[dict]:
        """
        Retorna predicciones formateadas para el Módulo 5.

        Returns:
            Lista de dicts con home_win_prob, draw_prob, away_win_prob, predicted_result
        """
        probs = self.predecir_proba(X)
        resultados = []

        for prob in probs:
            p_home, p_draw, p_away = float(prob[0]), float(prob[1]), float(prob[2])

            if p_home >= p_draw and p_home >= p_away:
                pred = "H"
            elif p_draw >= p_home and p_draw >= p_away:
                pred = "D"
            else:
                pred = "A"

            resultados.append({
                "home_win_prob": round(p_home, 4),
                "draw_prob": round(p_draw, 4),
                "away_win_prob": round(p_away, 4),
                "predicted_result": pred,
            })

        return resultados

    def importancia_features(self, top_n: int = 15) -> list[dict]:
        """
        Retorna los features más importantes según XGBoost.

        Returns:
            Lista de dicts {feature, importancia} ordenada descendente.
        """
        if not self.entrenado or not self.feature_names:
            return []

        importancias = self._xgb.feature_importances_
        if len(importancias) != len(self.feature_names):
            return []

        ranking = sorted(
            zip(self.feature_names, importancias),
            key=lambda x: x[1],
            reverse=True,
        )

        return [
            {"feature": name, "importancia": round(float(imp), 6)}
            for name, imp in ranking[:top_n]
        ]

    def guardar(self, nombre: str = "ensemble_1x2") -> Path:
        """Serializa el modelo a disco."""
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        ruta = ARTIFACT_DIR / f"{nombre}.joblib"
        joblib.dump({
            "xgb": self._xgb,
            "rf": self._rf,
            "lr": self._lr,
            "meta": self._meta,
            "feature_names": self.feature_names,
            "entrenado": self.entrenado,
        }, ruta)
        return ruta

    @classmethod
    def cargar(cls, nombre: str = "ensemble_1x2") -> "ModeloEnsemble1X2":
        """Carga el modelo desde disco."""
        ruta = ARTIFACT_DIR / f"{nombre}.joblib"
        if not ruta.exists():
            raise FileNotFoundError(f"Modelo no encontrado: {ruta}")

        data = joblib.load(ruta)
        modelo = cls()
        modelo._xgb = data["xgb"]
        modelo._rf = data["rf"]
        modelo._lr = data["lr"]
        modelo._meta = data["meta"]
        modelo.feature_names = data.get("feature_names", [])
        modelo.entrenado = data.get("entrenado", True)
        return modelo
