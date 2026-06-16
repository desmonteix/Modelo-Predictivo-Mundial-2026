"""
Script de Ingestión: Dataset Abierto (martj42/international_results)
===================================================================
Descarga el dataset histórico de resultados internacionales (CSV) y
puebla la base de datos con los amistosos y clasificatorias recientes.
Esta es una solución 100% gratuita que reemplaza a las APIs de pago.
"""

import argparse
import os
import sys
import pandas as pd
from datetime import datetime

import psycopg2

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.repositories import IngestionRepository

DATASET_URL = "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://predictor:predictor_pass@localhost:5432/predictor_futbol"
).replace("postgresql+asyncpg://", "postgresql://")

def ingestar_csv(db_url: str, start_year: int = 2024):
    print("📥 Descargando dataset de resultados internacionales...")
    df = pd.read_csv(DATASET_URL)
    
    # Filtrar datos válidos desde el año de inicio
    df['date'] = pd.to_datetime(df['date'])
    df = df[(df['date'].dt.year >= start_year) & (df['home_score'].notna()) & (df['away_score'].notna())].copy()
    
    print(f"📊 {len(df)} partidos encontrados desde {start_year}.")
    
    repo = IngestionRepository(db_url)
    
    # Mapeo en memoria para evitar saturar la BD con SELECTs
    team_cache = {}
    
    def get_team_id(name: str):
        if name in team_cache:
            return team_cache[name]
        tid = repo.get_internal_team_id_by_name(name)
        if tid:
            team_cache[name] = tid
        return tid

    inserted = 0
    skipped = 0

    print("Procesando e insertando en la Base de Datos...")
    for idx, row in df.iterrows():
        home_name = row['home_team']
        away_name = row['away_team']
        
        home_id = get_team_id(home_name)
        away_id = get_team_id(away_name)
        
        if not home_id or not away_id:
            skipped += 1
            continue
            
        date_str = row['date'].strftime("%Y-%m-%d")
        tournament = row['tournament']
        home_score = int(row['home_score'])
        away_score = int(row['away_score'])
        
        # League genérica para amistosos/otros
        league_id = repo.upsert_league(hash(tournament) % 100000, tournament)
        
        # Generar un ID externo ficticio basado en fecha y equipos para evitar duplicados
        ext_id = f"csv_{date_str}_{home_id}_{away_id}"
        
        importance = 0.5 if "Friendly" in tournament else 0.8
        
        repo.upsert_match(
            api_id=ext_id, # Usamos string, el repositorio debe soportarlo o el schema DB debe tener external_id VARCHAR
            date_str=date_str,
            season=str(row['date'].year),
            league_id=league_id,
            home_id=home_id,
            away_id=away_id,
            home_goals=home_score,
            away_goals=away_score,
            status="FT",
            stage="Regular",
            importance=importance
        )
        inserted += 1
        
        if inserted % 100 == 0:
            repo.commit()
            print(f"  ... {inserted} partidos procesados")
            
    repo.commit()
    repo.close()
    
    print(f"\n🎉 Ingestión CSV completada!")
    print(f"✅ Partidos insertados: {inserted}")
    print(f"⏭ Partidos ignorados (equipos no relevantes): {skipped}")
    print("💡 Ejecuta 'python scripts/recalc_elo.py' para actualizar el ranking con esta nueva data.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingesta resultados desde CSV Open Source")
    parser.add_argument("--start-year", type=int, default=2024, help="Año desde el cual importar")
    parser.add_argument("--db-url", default=DATABASE_URL)
    args = parser.parse_args()
    
    ingestar_csv(args.db_url, args.start_year)
