"""
Router de Predicciones — POST /api/v1/predict
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from db.connection import get_db
from schemas.prediction import (
    PrediccionCompleta,
    SolicitudPrediccionRapida,
    InfoPartido,
    TodasPredicciones,
    PrediccionGoles,
    PrediccionGolesTotal,
    PrediccionResultado,
    PrediccionGanador,
    PrediccionCorners,
    PrediccionFaltas,
    NivelConfianza,
    nivel_confianza,
)
import os
import joblib
from pathlib import Path
from models.dixon_coles import ModeloDixonColes
from models.xgboost_result import ModeloEnsemble1X2
from models.corners_fouls_model import ModeloCorners, ModeloFaltas
from features.temporal_decay import calcular_peso_partido

router = APIRouter()

ARTIFACT_DIR = Path(os.getenv("ARTIFACT_DIR", "/app/artifacts/models"))

# ─────────────────────────────────────────────────────────────
# Instancias de modelos (singleton por proceso)
# ─────────────────────────────────────────────────────────────

try:
    _ensemble_1x2 = ModeloEnsemble1X2.cargar("ensemble_1x2_v1")
    print("✓ Modelo XGBoost cargado exitosamente.")
except Exception:
    print("⚠ Modelo XGBoost no encontrado. Usando fallback.")
    _ensemble_1x2 = ModeloEnsemble1X2()

try:
    _dixon_coles = joblib.load(ARTIFACT_DIR / "dixon_coles_v1.joblib")
    print("✓ Modelo Dixon-Coles cargado exitosamente.")
except Exception:
    print("⚠ Modelo Dixon-Coles no encontrado. Usando fallback.")
    _dixon_coles = ModeloDixonColes()
try:
    _corners = joblib.load(ARTIFACT_DIR / "corners_v1.joblib")
    print("✓ Modelo Corners cargado exitosamente.")
except Exception:
    print("⚠ Modelo Corners no encontrado. Usando fallback.")
    _corners = ModeloCorners()

try:
    _faltas = joblib.load(ARTIFACT_DIR / "faltas_v1.joblib")
    print("✓ Modelo Faltas cargado exitosamente.")
except Exception:
    print("⚠ Modelo Faltas no encontrado. Usando fallback.")
    _faltas = ModeloFaltas()


def _build_prediccion_demo(
    home_team: str,
    away_team: str,
    league: str,
    match_stage: Optional[str] = None,
    is_neutral: bool = False,
) -> PrediccionCompleta:
    """
    Genera una predicción de demostración cuando no hay datos históricos.
    Usa promedios del Mundial FIFA como base.
    """
    # Promedios del Mundial FIFA (histórico 1990-2022)
    avg_goals_home = 1.4 if not is_neutral else 1.2
    avg_goals_away = 1.1

    # Resultado Dixon-Coles (fallback Poisson)
    dc_result = _dixon_coles.fallback_poisson(avg_goals_home, avg_goals_away)

    # Corners (Mundial: ~9.8 promedio)
    corners_home = 4.8
    corners_away = 4.2
    total_corners = 9.0

    # Faltas (Mundial: ~24 promedio)
    faltas_home = 12.1
    faltas_away = 11.9
    total_faltas = 24.0

    # 1X2 (sin datos de equipo → distribución prior del Mundial)
    p_home = 0.43 if not is_neutral else 0.37
    p_draw = 0.27
    p_away = 1.0 - p_home - p_draw

    goals_home = dc_result["goals_home"]
    goals_away = dc_result["goals_away"]
    total_goals = dc_result["total_goals"]

    return PrediccionCompleta(
        match=InfoPartido(
            home_team=home_team,
            away_team=away_team,
            league=league,
            date=datetime.now().strftime("%Y-%m-%d %H:%M"),
            match_stage=match_stage,
            data_quality_score=0.45,
        ),
        predictions=TodasPredicciones(
            goals_home=PrediccionGoles(
                value=goals_home["value"],
                most_likely=goals_home["most_likely"],
                distribution=goals_home["distribution"],
                confidence=0.50,
                confidence_label=NivelConfianza.BAJO,
            ),
            goals_away=PrediccionGoles(
                value=goals_away["value"],
                most_likely=goals_away["most_likely"],
                distribution=goals_away["distribution"],
                confidence=0.50,
                confidence_label=NivelConfianza.BAJO,
            ),
            total_goals=PrediccionGolesTotal(
                value=total_goals["value"],
                over_2_5_prob=total_goals["over_2_5_prob"],
                under_2_5_prob=total_goals["under_2_5_prob"],
                most_likely_range=total_goals["most_likely_range"],
                confidence=0.48,
                confidence_label=NivelConfianza.BAJO,
            ),
            result_1X2=PrediccionResultado(
                home_win_prob=round(p_home, 4),
                draw_prob=round(p_draw, 4),
                away_win_prob=round(p_away, 4),
                predicted_result="H" if p_home > max(p_draw, p_away) else ("D" if p_draw > p_away else "A"),
                confidence=0.50,
                confidence_label=NivelConfianza.BAJO,
            ),
            winner=PrediccionGanador(
                predicted=home_team if p_home > p_away else away_team,
                probability=round(max(p_home, p_away), 4),
                confidence_label=NivelConfianza.BAJO,
            ),
            corners=PrediccionCorners(
                value=total_corners,
                home_corners=corners_home,
                away_corners=corners_away,
                over_9_5_prob=0.46,
                over_11_5_prob=0.28,
                confidence=0.40,
                confidence_label=NivelConfianza.BAJO,
            ),
            fouls=PrediccionFaltas(
                value=total_faltas,
                home_fouls=faltas_home,
                away_fouls=faltas_away,
                over_20_5_prob=0.62,
                referee_impact="medio",
                confidence=0.35,
                confidence_label=NivelConfianza.BAJO,
            ),
            exact_scores=dc_result.get("exact_scores", [])
        ),
        key_factors=["Predicción basada en promedios del torneo (falta de datos)"],
        warnings=["No se encontraron datos históricos para estos equipos."],
        generated_at=datetime.now(),
        model_version="1.0.0",
    )


@router.post(
    "/predict",
    response_model=PrediccionCompleta,
    summary="Predecir resultado de un partido",
    description="Genera predicciones completas (goles, resultado, corners, faltas) para un partido.",
)
async def predecir_partido(
    solicitud: SolicitudPrediccionRapida,
    db: AsyncSession = Depends(get_db),
):
    """
    Endpoint principal de predicción.
    Acepta nombres de equipos y devuelve el output completo del Módulo 5.
    """
    try:
        # Buscar equipos en la BD
        query_home = text(
            "SELECT team_id, name FROM teams WHERE LOWER(name) LIKE LOWER(:name) LIMIT 1"
        )
        result_home = await db.execute(
            query_home, {"name": f"%{solicitud.home_team_name}%"}
        )
        home_row = result_home.fetchone()

        result_away = await db.execute(
            query_home, {"name": f"%{solicitud.away_team_name}%"}
        )
        away_row = result_away.fetchone()

        # Si los equipos están en la BD, generar predicción con datos reales
        if home_row and away_row:
            return await _predecir_con_datos(
                home_team_id=home_row.team_id,
                away_team_id=away_row.team_id,
                home_team_name=home_row.name,
                away_team_name=away_row.name,
                league=solicitud.league_name,
                match_stage=solicitud.match_stage,
                is_neutral=solicitud.is_neutral,
                db=db,
            )
        else:
            # Modo demo sin datos de equipo
            return _build_prediccion_demo(
                home_team=solicitud.home_team_name,
                away_team=solicitud.away_team_name,
                league=solicitud.league_name,
                match_stage=solicitud.match_stage,
                is_neutral=solicitud.is_neutral,
            )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generando predicción: {str(e)}"
        )


async def _predecir_con_datos(
    home_team_id: int,
    away_team_id: int,
    home_team_name: str,
    away_team_name: str,
    league: str,
    match_stage: Optional[str],
    is_neutral: bool,
    db: AsyncSession,
) -> PrediccionCompleta:
    """
    Genera predicción usando datos históricos de la BD.
    """
    from datetime import date
    today = date.today()

    # ── Obtener historial de partidos de cada equipo ───────────
    query_historial = text("""
        SELECT
            m.match_id, m.date, m.home_team_id, m.away_team_id,
            m.home_goals, m.away_goals, m.home_corners, m.away_corners,
            m.home_fouls, m.away_fouls, m.result, m.match_stage,
            COALESCE(s.xg, 0) as xg, COALESCE(s.xga, 0) as xga,
            COALESCE(s.corners_for, 0) as corners_for,
            COALESCE(s.fouls_committed, 0) as fouls_committed
        FROM matches m
        LEFT JOIN team_stats_per_match s
            ON s.match_id = m.match_id AND s.team_id = :team_id
        WHERE (m.home_team_id = :team_id OR m.away_team_id = :team_id)
          AND m.is_completed = TRUE
        ORDER BY m.date DESC
        LIMIT 20
    """)

    home_hist = (await db.execute(query_historial, {"team_id": home_team_id})).fetchall()
    away_hist = (await db.execute(query_historial, {"team_id": away_team_id})).fetchall()

    # ── Calcular pesos temporales y medias ponderadas ──────────
    def calcular_medias(partidos, team_id):
        if not partidos:
            return {"goles_favor": 1.2, "goles_contra": 1.2, "corners": 5.0, "faltas": 11.0, "xg": 1.2}

        goles_f, goles_c, corners_list, faltas_list, xg_list, pesos = [], [], [], [], [], []

        for p in partidos:
            peso = calcular_peso_partido(p.date.date() if hasattr(p.date, "date") else p.date, match_stage=p.match_stage)
            if peso < 0.05:
                continue

            es_local = p.home_team_id == team_id
            gf = p.home_goals if es_local else p.away_goals
            gc = p.away_goals if es_local else p.home_goals
            cf = p.home_corners if es_local else p.away_corners

            if gf is not None:
                goles_f.append(gf * peso)
                goles_c.append(gc * peso)
                
                # Estimate corners/fouls if data is missing based on goals
                est_corners = 3.5 + (gf * 1.5)
                est_faltas = 8.5 + (gc * 2.5)
                
                corners_list.append(cf * peso if cf else est_corners * peso)
                faltas_list.append(p.fouls_committed * peso if p.fouls_committed else est_faltas * peso)
                xg_list.append(p.xg * peso if p.xg else gf * peso)
                pesos.append(peso)

        if not pesos:
            return {"goles_favor": 1.2, "goles_contra": 1.2, "corners": 5.0, "faltas": 11.0, "xg": 1.2}

        total_peso = sum(pesos)
        return {
            "goles_favor": sum(goles_f) / total_peso,
            "goles_contra": sum(goles_c) / total_peso,
            "corners": sum(corners_list) / total_peso,
            "faltas": sum(faltas_list) / total_peso,
            "xg": sum(xg_list) / total_peso,
        }

    home_stats = calcular_medias(home_hist, home_team_id)
    away_stats = calcular_medias(away_hist, away_team_id)

    # ── ELO de ambos equipos ───────────────────────────────────
    query_elo = text("""
        SELECT elo_rating FROM team_form
        WHERE team_id = :team_id
        ORDER BY as_of_date DESC LIMIT 1
    """)
    home_elo_row = (await db.execute(query_elo, {"team_id": home_team_id})).fetchone()
    away_elo_row = (await db.execute(query_elo, {"team_id": away_team_id})).fetchone()
    home_elo = home_elo_row.elo_rating if home_elo_row else 1500.0
    away_elo = away_elo_row.elo_rating if away_elo_row else 1500.0
    elo_diff = home_elo - away_elo

    # ── Impacto de Jugadores (Scraper) ─────────────────────────
    from services.player_impact import player_impact_service
    home_player_impact = player_impact_service.get_team_impact(home_team_name, elo=home_elo)
    away_player_impact = player_impact_service.get_team_impact(away_team_name, elo=away_elo)

    # ── Dixon-Coles con parámetros del equipo ─────────────────
    home_advantage = 1.15 if not is_neutral else 1.0
    lambda_home = max(0.5, home_stats["xg"] * home_advantage)
    lambda_away = max(0.5, away_stats["xg"])

    # Ajuste ELO: diferencia de 100 puntos ≈ 10% más goles (SOLO PARA FALLBACK)
    elo_factor_home = 1 + (elo_diff / 1000)
    elo_factor_away = 1 - (elo_diff / 1000)
    
    # Impacto individual puro basado en jugadores (Wikipedia)
    player_mod_home = home_player_impact["offensive_impact"] * (2.0 - away_player_impact["defensive_impact"])
    player_mod_away = away_player_impact["offensive_impact"] * (2.0 - home_player_impact["defensive_impact"])

    # Suavizamos el impacto individual para que no sea tan extremo en el modelo entrenado (30% de peso)
    dixon_mod_home = 1.0 + (player_mod_home - 1.0) * 0.3
    dixon_mod_away = 1.0 + (player_mod_away - 1.0) * 0.3

    if _dixon_coles.tiene_parametros(home_team_id) and _dixon_coles.tiene_parametros(away_team_id):
        dc_result = _dixon_coles.predecir(
            home_team_id, 
            away_team_id, 
            es_neutral=is_neutral,
            home_modifier=dixon_mod_home,
            away_modifier=dixon_mod_away
        )
    else:
        # Fallback usa la data media combinada con ELO y el impacto individual
        lambda_home *= (elo_factor_home * player_mod_home)
        lambda_away *= (elo_factor_away * player_mod_away)
        
        # Limitador de sanidad
        lambda_home = max(0.05, lambda_home)
        lambda_away = max(0.05, lambda_away)
        
        dc_result = _dixon_coles.fallback_poisson(lambda_home, lambda_away)

    # ── Resultado 1X2 ──────────────────────────────────────────
    # ── XGBoost Ensemble (Fallback si no hay suficiente data) ──
    # Se usa XGBoost si el partido es nivelado (elo_diff < 250)
    # PERO, si el impacto de jugadores modifica drásticamente los goles esperados
    # (ej. goles > 2.5), forzamos a que Dixon-Coles dicte las probabilidades
    # ya que XGBoost ignora el player_impact_service.
    dixon_probs = dc_result["result_1x2_dixon"]
    usar_xgboost = _ensemble_1x2.entrenado and abs(elo_diff) < 250 and len(home_hist) >= 3 and len(away_hist) >= 3
    
    if usar_xgboost and dc_result["goals_home"]["value"] < 2.5 and dc_result["goals_away"]["value"] < 2.5:
        # Features: 'elo_diff', 'xg_diff', 'xga_diff', 'corners_diff', 'clean_sheets_diff', 'home_injury', 'away_injury'
        X_pred = np.array([[
            elo_diff,
            home_stats["xg"] - away_stats["xg"],
            home_stats["goles_contra"] - away_stats["goles_contra"], # Aproximación de xga_diff
            home_stats["corners"] - away_stats["corners"],
            0, # clean_sheets_diff
            0, # home_injury_impact
            0  # away_injury_impact
        ]])
        probs = _ensemble_1x2.predecir_proba(X_pred)[0]
        p_home, p_draw, p_away = float(probs[0]), float(probs[1]), float(probs[2])
    else:
        # Usar la probabilidad extraída de Dixon-Coles como fallback
        dixon_probs = dc_result["result_1x2_dixon"]
        p_home = dixon_probs["home_win_prob"]
        p_draw = dixon_probs["draw_prob"]
        p_away = dixon_probs["away_win_prob"]

    pred_result = "H" if p_home >= p_draw and p_home >= p_away else ("D" if p_draw >= p_away else "A")
    max_p = max(p_home, p_draw, p_away)

    # ── Confianza basada en cantidad de datos ──────────────────
    n_datos = min(len(home_hist), len(away_hist))
    base_conf = min(0.85, 0.50 + n_datos * 0.02)

    # ── Corners y Faltas ───────────────────────────────────────
    X_pred_cf = np.array([home_stats["xg"], away_stats["xg"]])
    
    res_corners = _corners.predecir(
        X=X_pred_cf,
        home_corners_hist=home_stats["corners"],
        away_corners_hist=away_stats["corners"],
    )
    
    res_faltas = _faltas.predecir(
        X=X_pred_cf,
        home_faltas_hist=home_stats["faltas"],
        away_faltas_hist=away_stats["faltas"],
        arbitro_strictness=5.0,
        es_rivalidad_alta=False,
    )

    # ── Key factors ────────────────────────────────────────────
    key_factors = []
    
    # Justificación visual del impacto de jugadores
    home_att_name = home_player_impact["key_attacker"]["name"]
    away_att_name = away_player_impact["key_attacker"]["name"]
    if home_player_impact["offensive_impact"] > 1.1:
        key_factors.append(f"El ataque de {home_team_name} es letal (Liderado por {home_att_name})")
    elif home_player_impact["offensive_impact"] < 0.8:
        key_factors.append(f"El ataque de {home_team_name} está en muy mala racha")
        
    if away_player_impact["offensive_impact"] > 1.1:
        key_factors.append(f"El ataque de {away_team_name} es letal (Liderado por {away_att_name})")
    elif away_player_impact["offensive_impact"] < 0.8:
        key_factors.append(f"El ataque de {away_team_name} está en muy mala racha")

    if len(home_hist) >= 5:
        recent = home_hist[:5]
        wins = sum(1 for p in recent if (p.result == "H" and p.home_team_id == home_team_id) or (p.result == "A" and p.away_team_id == home_team_id))
        if wins >= 3:
            key_factors.append(f"{home_team_name} ganó {wins} de sus últimos 5 partidos")
    if abs(elo_diff) > 100:
        equipo_mejor = home_team_name if elo_diff > 0 else away_team_name
        key_factors.append(f"{equipo_mejor} tiene ventaja ELO de {abs(elo_diff):.0f} puntos")
    if not is_neutral:
        key_factors.append(f"Ventaja de localía aplicada para {home_team_name}")

    # ── Warnings ───────────────────────────────────────────────
    warnings_list = []
    if n_datos < 5:
        warnings_list.append(f"Datos históricos limitados: solo {n_datos} partido(s) encontrado(s)")
    if not home_hist:
        warnings_list.append(f"Sin historial disponible para {home_team_name}")
    if not away_hist:
        warnings_list.append(f"Sin historial disponible para {away_team_name}")

    goals_home = dc_result["goals_home"]
    goals_away = dc_result["goals_away"]
    total_goals = dc_result["total_goals"]

    return PrediccionCompleta(
        match=InfoPartido(
            home_team=home_team_name,
            away_team=away_team_name,
            league=league,
            date=datetime.now().strftime("%Y-%m-%d %H:%M"),
            match_stage=match_stage,
            data_quality_score=round(min(0.95, 0.50 + n_datos * 0.025), 2),
        ),
        predictions=TodasPredicciones(
            goals_home=PrediccionGoles(
                value=goals_home["value"],
                most_likely=goals_home["most_likely"],
                distribution=goals_home["distribution"],
                confidence=round(base_conf * 0.95, 2),
                confidence_label=nivel_confianza(base_conf * 0.95),
            ),
            goals_away=PrediccionGoles(
                value=goals_away["value"],
                most_likely=goals_away["most_likely"],
                distribution=goals_away["distribution"],
                confidence=round(base_conf * 0.92, 2),
                confidence_label=nivel_confianza(base_conf * 0.92),
            ),
            total_goals=PrediccionGolesTotal(
                value=total_goals["value"],
                over_2_5_prob=total_goals["over_2_5_prob"],
                under_2_5_prob=total_goals["under_2_5_prob"],
                most_likely_range=total_goals["most_likely_range"],
                confidence=round(base_conf * 0.90, 2),
                confidence_label=nivel_confianza(base_conf * 0.90),
            ),
            result_1X2=PrediccionResultado(
                home_win_prob=round(p_home, 4),
                draw_prob=round(p_draw, 4),
                away_win_prob=round(p_away, 4),
                predicted_result=pred_result,
                confidence=round(base_conf, 2),
                confidence_label=nivel_confianza(base_conf),
            ),
            winner=PrediccionGanador(
                predicted=home_team_name if p_home >= p_away else away_team_name,
                probability=round(max(p_home, p_away), 4),
                confidence_label=nivel_confianza(base_conf * 0.9),
            ),
            corners=PrediccionCorners(
                value=res_corners["value"],
                home_corners=res_corners["home_corners"],
                away_corners=res_corners["away_corners"],
                over_9_5_prob=res_corners["over_9_5_prob"],
                over_11_5_prob=res_corners["over_11_5_prob"],
                confidence=round(base_conf * 0.85, 2),
                confidence_label=nivel_confianza(base_conf * 0.85),
            ),
            fouls=PrediccionFaltas(
                value=res_faltas["value"],
                home_fouls=res_faltas["home_fouls"],
                away_fouls=res_faltas["away_fouls"],
                over_20_5_prob=res_faltas["over_20_5_prob"],
                referee_impact=res_faltas["referee_impact"],
                confidence=round(base_conf * 0.82, 2),
                confidence_label=nivel_confianza(base_conf * 0.82),
            ),
            exact_scores=dc_result.get("exact_scores", [])
        ),
        key_factors=key_factors or ["Predicción basada en historial ponderado temporalmente"],
        warnings=warnings_list,
        generated_at=datetime.now(),
        model_version="1.0.0",
    )


@router.get(
    "/predictions",
    summary="Listar predicciones recientes",
)
async def listar_predicciones(
    limite: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """Lista las predicciones más recientes almacenadas."""
    result = await db.execute(
        text("""
            SELECT p.prediction_id, m.date,
                   ht.name as home_team, at.name as away_team,
                   p.predicted_result, p.home_win_prob, p.draw_prob, p.away_win_prob,
                   p.was_correct_result, p.generated_at
            FROM predictions p
            JOIN matches m ON p.match_id = m.match_id
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            ORDER BY p.generated_at DESC
            LIMIT :limite
        """),
        {"limite": limite},
    )
    rows = result.fetchall()
    return [dict(row._mapping) for row in rows]
