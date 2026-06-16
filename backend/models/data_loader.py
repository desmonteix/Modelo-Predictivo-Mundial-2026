"""
Cargador de Datos para Modelos ML (Módulo 3)
=============================================
Extrae datos limpios de PostgreSQL para alimentar a Dixon-Coles y XGBoost.
"""

import os
from typing import Dict, List, Tuple
import pandas as pd
import numpy as np
import psycopg2

class DataLoader:
    def __init__(self, db_url: str = None):
        self.db_url = db_url or os.getenv(
            "DATABASE_URL", 
            "postgresql://predictor:predictor_pass@localhost:5432/predictor_futbol"
        ).replace("postgresql+asyncpg://", "postgresql://")

    def get_connection(self):
        return psycopg2.connect(self.db_url)

    def load_dixon_coles_data(self) -> List[Dict]:
        """
        Extrae datos para entrenar el modelo de Poisson bivariado.
        Limita a los últimos 12 partidos por selección.
        Aplica decaimiento temporal y potenciador por ELO del rival.
        """
        query = """
            WITH RankedMatchesHome AS (
                SELECT match_id, ROW_NUMBER() OVER(PARTITION BY home_team_id ORDER BY date DESC) as rn_home
                FROM matches WHERE is_completed = TRUE
            ),
            RankedMatchesAway AS (
                SELECT match_id, ROW_NUMBER() OVER(PARTITION BY away_team_id ORDER BY date DESC) as rn_away
                FROM matches WHERE is_completed = TRUE
            )
            SELECT 
                m.home_team_id as home_id, 
                m.away_team_id as away_id, 
                m.home_goals, 
                m.away_goals,
                m.date,
                m.match_importance,
                COALESCE(tf_home.elo_rating, 1500) AS home_elo,
                COALESCE(tf_away.elo_rating, 1500) AS away_elo
            FROM matches m
            JOIN RankedMatchesHome rh ON m.match_id = rh.match_id
            JOIN RankedMatchesAway ra ON m.match_id = ra.match_id
            LEFT JOIN team_form tf_home ON m.home_team_id = tf_home.team_id AND tf_home.as_of_date <= m.date::date
            LEFT JOIN team_form tf_away ON m.away_team_id = tf_away.team_id AND tf_away.as_of_date <= m.date::date
            WHERE m.is_completed = TRUE 
            AND m.home_goals IS NOT NULL 
            AND m.away_goals IS NOT NULL
            AND (rh.rn_home <= 12 OR ra.rn_away <= 12)
        """
        with self.get_connection() as conn:
            df = pd.read_sql_query(query, conn)
            
        if df.empty:
            return []
            
        # Calcular pesos en Python
        # 1. Decaimiento Temporal: partidos recientes valen más
        # max_date es el partido más reciente en la BD
        max_date = pd.to_datetime(df['date'], utc=True).max()
        days_diff = (max_date - pd.to_datetime(df['date'], utc=True)).dt.days
        # Decaimiento exponencial suave (vida media ~2 años si usamos 0.001)
        time_decay = np.exp(-0.0015 * days_diff)
        
        # 2. Potenciador ELO (Ranking FIFA proxy): no es lo mismo ganarle a Alemania que a Haití
        # Calculamos el promedio de ELO del partido vs un ELO base de 1500
        avg_match_elo = (df['home_elo'] + df['away_elo']) / 2.0
        # ELO de 1800 (Top mundial) -> multiplicador ~1.2. ELO de 1200 -> multiplicador ~0.8
        elo_boost = np.clip(avg_match_elo / 1500.0, 0.5, 1.5)
        
        # 3. Importancia del partido (Amistosos pesan menos)
        match_importance = df['match_importance'].fillna(1.0)
        
        df['weight'] = time_decay * elo_boost * match_importance
        
        # Seleccionar columnas finales
        result_df = df[['home_id', 'away_id', 'home_goals', 'away_goals', 'weight']]
        return result_df.to_dict(orient='records')

    def load_xgboost_data(self) -> Tuple[np.ndarray, List[str], List[str]]:
        """
        Construye la matriz de features X y las etiquetas y para XGBoost.
        También limita el dataset a los últimos 12 partidos por equipo.
        """
        query = """
            WITH RankedMatchesHome AS (
                SELECT match_id, ROW_NUMBER() OVER(PARTITION BY home_team_id ORDER BY date DESC) as rn_home
                FROM matches WHERE is_completed = TRUE
            ),
            RankedMatchesAway AS (
                SELECT match_id, ROW_NUMBER() OVER(PARTITION BY away_team_id ORDER BY date DESC) as rn_away
                FROM matches WHERE is_completed = TRUE
            )
            SELECT 
                m.match_id,
                m.result,
                -- Features (Diferencias relativas entre local y visitante)
                COALESCE(tf_home.elo_rating, 1500) - COALESCE(tf_away.elo_rating, 1500) AS elo_diff,
                COALESCE(tf_home.last5_xg, 1.0) - COALESCE(tf_away.last5_xg, 1.0) AS xg_diff,
                COALESCE(tf_home.last5_xga, 1.0) - COALESCE(tf_away.last5_xga, 1.0) AS xga_diff,
                COALESCE(tf_home.last5_corners, 4.0) - COALESCE(tf_away.last5_corners, 4.0) AS corners_diff,
                COALESCE(tf_home.last5_clean_sheets, 0) - COALESCE(tf_away.last5_clean_sheets, 0) AS clean_sheets_diff,
                
                -- Bajas de jugadores
                COALESCE(pa_home.injury_impact_score, 0) AS home_injury_impact,
                COALESCE(pa_away.injury_impact_score, 0) AS away_injury_impact
            FROM matches m
            JOIN RankedMatchesHome rh ON m.match_id = rh.match_id
            JOIN RankedMatchesAway ra ON m.match_id = ra.match_id
            LEFT JOIN team_form tf_home ON m.home_team_id = tf_home.team_id AND tf_home.as_of_date <= m.date::date
            LEFT JOIN team_form tf_away ON m.away_team_id = tf_away.team_id AND tf_away.as_of_date <= m.date::date
            LEFT JOIN players_availability pa_home ON m.home_team_id = pa_home.team_id AND m.match_id = pa_home.match_id
            LEFT JOIN players_availability pa_away ON m.away_team_id = pa_away.team_id AND m.match_id = pa_away.match_id
            WHERE m.is_completed = TRUE 
            AND m.result IS NOT NULL
            AND (rh.rn_home <= 12 OR ra.rn_away <= 12)
        """
        
        with self.get_connection() as conn:
            df = pd.read_sql_query(query, conn)
        
        if df.empty:
            return np.array([]), [], []

        # Rellenar NaNs con 0 (o promedio histórico) para no perder filas enteras
        df.fillna(0, inplace=True)
        
        y = df['result'].tolist()
        feature_cols = [
            'elo_diff', 'xg_diff', 'xga_diff', 'corners_diff', 
            'clean_sheets_diff', 'home_injury_impact', 'away_injury_impact'
        ]
        X = df[feature_cols].values
        
        return X, y, feature_cols
