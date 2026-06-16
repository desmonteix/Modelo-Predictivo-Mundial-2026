"""
Script de Ingestión: "Last 12 Matches" por equipo usando football-data.org
Descarga los últimos 12 partidos de las selecciones principales.
Respeta el rate limit de 10 peticiones por minuto.
"""

import argparse
import os
import sys
import time
from datetime import datetime

import psycopg2

# Añadir el backend al path para importar
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.ingest_world_cup import FootballDataClient

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://predictor:predictor_pass@localhost:5432/predictor_futbol"
).replace("postgresql+asyncpg://", "postgresql://")

class IngestorUltimosPartidos:
    def __init__(self, db_url: str, api_key: str):
        self.conn = psycopg2.connect(db_url)
        self.client = FootballDataClient(api_key)

    def _upsert_partido(self, cursor, match: dict, league_id: int):
        """Inserta o actualiza un partido usando el formato de football-data.org."""
        home = match.get("homeTeam", {})
        away = match.get("awayTeam", {})
        score = match.get("score", {})
        ft = score.get("fullTime", {})
        ht = score.get("halfTime", {})

        cursor.execute("SELECT team_id FROM teams WHERE external_id = %s", (str(home.get("id")),))
        home_row = cursor.fetchone()
        cursor.execute("SELECT team_id FROM teams WHERE external_id = %s", (str(away.get("id")),))
        away_row = cursor.fetchone()

        if not home_row or not away_row:
            return

        home_id = home_row[0]
        away_id = away_row[0]

        home_goals = ft.get("home")
        away_goals = ft.get("away")

        result = None
        if home_goals is not None and away_goals is not None:
            if home_goals > away_goals:
                result = "H"
            elif home_goals == away_goals:
                result = "D"
            else:
                result = "A"

        stage = match.get("stage", "REGULAR_SEASON").replace("_", " ").title()
        is_completed = match.get("status") == "FINISHED"

        importance = 0.5 if "Friendlies" in match.get("competition", {}).get("name", "") else 0.8
        
        match_date = match.get("utcDate", "")
        if match_date:
            match_date = datetime.fromisoformat(match_date.replace("Z", "+00:00"))
        else:
            return

        season_str = str(match.get("season", {}).get("startDate", "2026")[:4])

        cursor.execute("""
            INSERT INTO matches (
                external_id, date, season, league_id,
                home_team_id, away_team_id,
                home_goals, away_goals,
                home_goals_ht, away_goals_ht,
                result, match_stage, match_importance,
                is_neutral_venue, is_completed, data_source
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (external_id) DO UPDATE SET
                home_goals = EXCLUDED.home_goals,
                away_goals = EXCLUDED.away_goals,
                result = EXCLUDED.result,
                is_completed = EXCLUDED.is_completed,
                updated_at = NOW()
        """, (
            str(match.get("id", "")),
            match_date,
            season_str,
            league_id,
            home_id,
            away_id,
            home_goals,
            away_goals,
            ht.get("home"),
            ht.get("away"),
            result,
            stage,
            importance,
            False,
            is_completed,
            "football-data.org",
        ))

    def ingestar(self, limit_teams: int):
        with self.conn.cursor() as cur:
            cur.execute("SELECT league_id FROM leagues WHERE name ILIKE '%World Cup%' LIMIT 1")
            row = cur.fetchone()
            if not row:
                print("❌ Liga World Cup no encontrada.")
                return
            league_id = row[0]

            cur.execute("""
                SELECT external_id, name 
                FROM teams 
                WHERE external_id IS NOT NULL 
                ORDER BY team_id ASC 
                LIMIT %s
            """, (limit_teams,))
            teams = cur.fetchall()

        print(f"Iniciando descarga de últimos partidos para {len(teams)} selecciones.")

        for t in teams:
            external_id = int(t[0])
            name = t[1]
            print(f"\n==================================================")
            print(f"📥 Descargando últimos partidos de: {name} (ID: {external_id})")
            print(f"==================================================")

            try:
                data = self.client._get(f"/teams/{external_id}/matches", {"limit": 12, "status": "FINISHED"})
                matches = data.get("matches", [])
                print(f"  ✓ {len(matches)} partidos obtenidos.")

                with self.conn.cursor() as cur:
                    for match in matches:
                        self._upsert_partido(cur, match, league_id)
                self.conn.commit()

            except Exception as e:
                print(f"  ⚠ Error con {name}: {e}")
                self.conn.rollback()

            time.sleep(6.5)  # 10 peticiones / minuto

        print("\n🎉 Ingestión completada.")

    def close(self):
        self.conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Descarga los últimos 12 partidos usando football-data.org")
    parser.add_argument("--api-key", default=os.getenv("FOOTBALL_DATA_API_KEY"), help="API Key")
    parser.add_argument("--db-url", default=DATABASE_URL)
    parser.add_argument("--limit-teams", type=int, default=50)

    args = parser.parse_args()

    if not args.api_key:
        print("❌ ERROR: API_KEY no configurada")
        exit(1)

    ingestador = IngestorUltimosPartidos(args.db_url, args.api_key)
    try:
        ingestador.ingestar(args.limit_teams)
    finally:
        ingestador.close()
    
    print("💡 Para actualizar el ranking tras descargar datos, ejecuta: python scripts/recalc_elo.py")
