"""
Schemas Pydantic — Módulo 5: Formato de Salida de Predicciones
"""

from __future__ import annotations
from typing import Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, validator


class NivelConfianza(str, Enum):
    ALTO = "alto"
    MEDIO = "medio"
    BAJO = "bajo"


def nivel_confianza(score: float) -> NivelConfianza:
    """Convierte un score numérico al nivel de confianza descriptivo."""
    if score >= 0.70:
        return NivelConfianza.ALTO
    elif score >= 0.55:
        return NivelConfianza.MEDIO
    else:
        return NivelConfianza.BAJO


# ─────────────────────────────────────────────────────────────
# Sub-esquemas de predicción
# ─────────────────────────────────────────────────────────────

class PrediccionGoles(BaseModel):
    value: float = Field(..., description="Goles esperados (valor flotante)")
    most_likely: int = Field(..., description="Número de goles más probable")
    distribution: dict[str, float] = Field(..., description="P(goles=k) para k=0,1,2,3+")
    confidence: float = Field(..., ge=0, le=1)
    confidence_label: NivelConfianza


class PrediccionGolesTotal(BaseModel):
    value: float
    over_2_5_prob: float = Field(..., ge=0, le=1)
    under_2_5_prob: float = Field(..., ge=0, le=1)
    most_likely_range: str = Field(..., example="2-3")
    confidence: float = Field(..., ge=0, le=1)
    confidence_label: NivelConfianza


class PrediccionResultado(BaseModel):
    home_win_prob: float = Field(..., ge=0, le=1)
    draw_prob: float = Field(..., ge=0, le=1)
    away_win_prob: float = Field(..., ge=0, le=1)
    predicted_result: str = Field(..., description="H (local), D (empate), A (visitante)")
    confidence: float = Field(..., ge=0, le=1)
    confidence_label: NivelConfianza

    @validator("predicted_result")
    def validar_resultado(cls, v):
        if v not in ("H", "D", "A"):
            raise ValueError("El resultado debe ser H, D o A")
        return v


class PrediccionGanador(BaseModel):
    predicted: str = Field(..., description="Nombre del equipo predicho como ganador")
    probability: float = Field(..., ge=0, le=1)
    confidence_label: NivelConfianza
    va_a_penales_prob: Optional[float] = None


class PrediccionCorners(BaseModel):
    value: float = Field(..., description="Total de corners esperados")
    home_corners: float
    away_corners: float
    over_9_5_prob: float = Field(..., ge=0, le=1)
    over_11_5_prob: float = Field(..., ge=0, le=1)
    confidence: float = Field(..., ge=0, le=1)
    confidence_label: NivelConfianza


class PrediccionFaltas(BaseModel):
    value: float = Field(..., description="Total de faltas esperadas")
    home_fouls: float
    away_fouls: float
    over_20_5_prob: float = Field(..., ge=0, le=1)
    referee_impact: str = Field(..., description="alto, medio o bajo")
    confidence: float = Field(..., ge=0, le=1)
    confidence_label: NivelConfianza


class PrediccionExactScore(BaseModel):
    home: int
    away: int
    prob: float = Field(..., ge=0, le=1)

class TodasPredicciones(BaseModel):
    goals_home: PrediccionGoles
    goals_away: PrediccionGoles
    total_goals: PrediccionGolesTotal
    result_1X2: PrediccionResultado
    winner: PrediccionGanador
    corners: PrediccionCorners
    fouls: PrediccionFaltas
    exact_scores: list[PrediccionExactScore] = []


# ─────────────────────────────────────────────────────────────
# Esquema principal de predicción (Módulo 5)
# ─────────────────────────────────────────────────────────────

class InfoPartido(BaseModel):
    home_team: str
    away_team: str
    league: str
    date: str
    match_stage: Optional[str] = None
    data_quality_score: float = Field(..., ge=0, le=1)


class PrediccionCompleta(BaseModel):
    match: InfoPartido
    predictions: TodasPredicciones
    key_factors: list[str] = Field(default_factory=list, max_items=10)
    warnings: list[str] = Field(default_factory=list, max_items=10)
    generated_at: datetime
    model_version: str = "1.0.0"


# ─────────────────────────────────────────────────────────────
# Schemas de request
# ─────────────────────────────────────────────────────────────

class SolicitudPrediccion(BaseModel):
    """Request para predecir un partido."""
    match_id: Optional[int] = Field(None, description="ID del partido en la BD")
    home_team_id: Optional[int] = None
    away_team_id: Optional[int] = None
    league_id: Optional[int] = None
    date: Optional[str] = None
    match_stage: Optional[str] = None
    is_neutral: bool = False

    class Config:
        json_schema_extra = {
            "example": {
                "match_id": 42,
                "is_neutral": False,
            }
        }


class SolicitudPrediccionRapida(BaseModel):
    """Request simplificado: nombres de equipos (para demo/UI)."""
    home_team_name: str
    away_team_name: str
    league_name: str = "FIFA World Cup"
    match_stage: Optional[str] = None
    is_neutral: bool = False


# ─────────────────────────────────────────────────────────────
# Schemas de respuesta de equipos y partidos
# ─────────────────────────────────────────────────────────────

class EquipoResumen(BaseModel):
    team_id: int
    name: str
    short_name: Optional[str]
    country: Optional[str]
    elo_rating: Optional[float]
    last5_results: Optional[str]


class PartidoResumen(BaseModel):
    match_id: int
    date: str
    home_team: str
    away_team: str
    league: str
    match_stage: Optional[str]
    home_goals: Optional[int]
    away_goals: Optional[int]
    result: Optional[str]
    is_completed: bool
    has_prediction: bool = False


class EstadisticasEquipo(BaseModel):
    team_id: int
    name: str
    elo_rating: float
    last5_results: Optional[str]
    last5_goals_scored: Optional[float]
    last5_goals_conceded: Optional[float]
    home_win_rate: Optional[float]
    away_win_rate: Optional[float]
    streak_type: Optional[str]
    streak_length: Optional[int]


class HealthResponse(BaseModel):
    status: str
    database: str
    redis: str
    modelos_cargados: list[str]
    version: str
    timestamp: datetime
