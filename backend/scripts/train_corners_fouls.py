"""
Script para entrenar modelos de Corners y Faltas
"""

import os
import sys
import asyncio
import joblib
import numpy as np
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.connection import AsyncSessionLocal
from sqlalchemy import text
from models.corners_fouls_model import ModeloCorners, ModeloFaltas

ARTIFACT_DIR = Path(os.getenv("ARTIFACT_DIR", "/app/artifacts/models"))

async def train():
    print("Obteniendo datos de la BD para entrenar corners y faltas...")
    
    async with AsyncSessionLocal() as db:
        query = text("""
            SELECT 
                m.home_corners, m.away_corners, 
                m.home_fouls, m.away_fouls,
                s1.corners_for as home_corners_stat, s1.fouls_committed as home_fouls_stat,
                s2.corners_for as away_corners_stat, s2.fouls_committed as away_fouls_stat,
                COALESCE(s1.xg, 1.2) as home_xg, COALESCE(s2.xg, 1.2) as away_xg
            FROM matches m
            LEFT JOIN team_stats_per_match s1 ON s1.match_id = m.match_id AND s1.team_id = m.home_team_id
            LEFT JOIN team_stats_per_match s2 ON s2.match_id = m.match_id AND s2.team_id = m.away_team_id
            WHERE m.is_completed = TRUE
        """)
        result = await db.execute(query)
        rows = result.fetchall()
        
    X_corners = []
    y_corners = []
    X_fouls = []
    y_fouls = []
    
    for row in rows:
        hc = row.home_corners or row.home_corners_stat
        ac = row.away_corners or row.away_corners_stat
        hf = row.home_fouls or row.home_fouls_stat
        af = row.away_fouls or row.away_fouls_stat
        
        home_xg = float(row.home_xg)
        away_xg = float(row.away_xg)
        
        if hc is not None and ac is not None:
            # Simple features for corners: home_xg, away_xg
            X_corners.append([home_xg, away_xg])
            y_corners.append(hc + ac)
            
        if hf is not None and af is not None:
            # Simple features for fouls: home_xg, away_xg
            X_fouls.append([home_xg, away_xg])
            y_fouls.append(hf + af)
            
    X_corners = np.array(X_corners)
    y_corners = np.array(y_corners)
    X_fouls = np.array(X_fouls)
    y_fouls = np.array(y_fouls)
    
    print(f"Datos de Corners: {len(X_corners)} partidos")
    print(f"Datos de Faltas: {len(X_fouls)} partidos")
    
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Entrenar Corners
    modelo_corners = ModeloCorners()
    if len(X_corners) > 0:
        res = modelo_corners.entrenar(X_corners, y_corners, verbose=True)
        print("Resultado Corners:", res)
        joblib.dump(modelo_corners, ARTIFACT_DIR / "corners_v1.joblib")
    
    # Entrenar Faltas
    modelo_faltas = ModeloFaltas()
    if len(X_fouls) > 0:
        res = modelo_faltas.entrenar(X_fouls, y_fouls, verbose=True)
        print("Resultado Faltas:", res)
        joblib.dump(modelo_faltas, ARTIFACT_DIR / "faltas_v1.joblib")
        
    print("Entrenamiento completado.")

if __name__ == "__main__":
    asyncio.run(train())
