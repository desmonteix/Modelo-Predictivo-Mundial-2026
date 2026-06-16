"""
Ingestión de datos del Mundial — football-data.org API
=======================================================
Pobla la base de datos con partidos del Mundial FIFA.

Uso:
  python data/ingest_world_cup.py --api-key TU_KEY --seasons 2018 2022

Requiere:
  - FOOTBALL_DATA_API_KEY en variables de entorno O argumento --api-key
  - Conexión directa a PostgreSQL (usa psycopg2 sync para simplicidad)

API gratuita en: https://www.football-data.org/client/register
Endpoint World Cup: GET /v4/competitions/WC/matches
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime
from typing import Optional

import httpx
import psycopg2
from psycopg2.extras import execute_values

# ─────────────────────────────────────────────────────────────
# Configuración
# ─────────────────────────────────────────────────────────────

API_BASE = "https://api.football-data.org/v4"
WORLD_CUP_CODE = "WC"

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://predictor:predictor_pass@localhost:5432/predictor_futbol"
).replace("postgresql+asyncpg://", "postgresql://")


# ─────────────────────────────────────────────────────────────
# Cliente API
# ─────────────────────────────────────────────────────────────

class FootballDataClient:
    def __init__(self, api_key: str):
        self.headers = {
            "X-Auth-Token": api_key,
            "Accept": "application/json",
        }
        self.client = httpx.Client(headers=self.headers, timeout=30.0)

    def _get(self, endpoint: str, params: dict = None) -> dict:
        url = f"{API_BASE}{endpoint}"
        print(f"  → GET {url}")
        response = self.client.get(url, params=params or {})

        if response.status_code == 429:
            print("  ⚠ Rate limit — esperando 60 segundos...")
            time.sleep(60)
            return self._get(endpoint, params)

        response.raise_for_status()
        return response.json()

    def get_competition_teams(self, competition_code: str, season: int) -> list[dict]:
        """Obtiene los equipos de una competición."""
        data = self._get(f"/competitions/{competition_code}/teams", {"season": season})
        return data.get("teams", [])

    def get_matches(self, competition_code: str, season: int, status: str = "FINISHED") -> list[dict]:
        """Obtiene los partidos de una competición."""
        params = {"season": season}
        if status != "ALL":
            params["status"] = status
        data = self._get(f"/competitions/{competition_code}/matches", params)
        return data.get("matches", [])


# ─────────────────────────────────────────────────────────────
# Procesamiento y carga en BD
# ─────────────────────────────────────────────────────────────

class IngestorMundial:
    def __init__(self, db_url: str, api_key: str):
        self.conn = psycopg2.connect(db_url)
        self.client = FootballDataClient(api_key)

    def _upsert_equipo(self, cursor, team: dict) -> int:
        """Inserta o actualiza un equipo, retorna team_id."""
        cursor.execute("""
            INSERT INTO teams (name, short_name, country, external_id)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (external_id) DO UPDATE SET
                name = EXCLUDED.name,
                short_name = EXCLUDED.short_name,
                updated_at = NOW()
            WHERE teams.external_id IS NOT NULL
            RETURNING team_id
        """, (
            team.get("name", "Unknown"),
            team.get("shortName") or team.get("tla", ""),
            team.get("area", {}).get("name", ""),
            str(team.get("id", "")),
        ))
        row = cursor.fetchone()
        if row:
            return row[0]

        # Si no hay RETURNING (porque no hubo INSERT ni UPDATE), buscar
        cursor.execute(
            "SELECT team_id FROM teams WHERE external_id = %s",
            (str(team.get("id", "")),)
        )
        row = cursor.fetchone()
        return row[0] if row else None

    def _upsert_partido(self, cursor, match: dict, league_id: int):
        """Inserta o actualiza un partido."""
        home = match.get("homeTeam", {})
        away = match.get("awayTeam", {})
        score = match.get("score", {})
        ft = score.get("fullTime", {})
        ht = score.get("halfTime", {})

        # Buscar team_ids por external_id
        cursor.execute("SELECT team_id FROM teams WHERE external_id = %s", (str(home.get("id")),))
        home_row = cursor.fetchone()
        cursor.execute("SELECT team_id FROM teams WHERE external_id = %s", (str(away.get("id")),))
        away_row = cursor.fetchone()

        if not home_row or not away_row:
            return  # Equipo no encontrado, saltar

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

        stage = match.get("stage", "GROUP_STAGE").replace("_", " ").title()
        is_completed = match.get("status") == "FINISHED"

        # Determinar importancia del partido
        importance = 0.7  # default
        stage_upper = match.get("stage", "").upper()
        if "FINAL" in stage_upper:
            importance = 1.0
        elif "SEMI" in stage_upper:
            importance = 0.95
        elif "QUARTER" in stage_upper:
            importance = 0.90
        elif "ROUND_OF_16" in stage_upper or "LAST_16" in stage_upper:
            importance = 0.85

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
            True,   # Mundial siempre en campo neutral
            is_completed,
            "football-data.org",
        ))

    def ingestar_mundial(self, seasons: list[int]):
        """Proceso principal de ingestión del Mundial."""
        with self.conn.cursor() as cur:
            # Obtener league_id del Mundial
            cur.execute("SELECT league_id FROM leagues WHERE external_id = '2000' OR name ILIKE '%World Cup%' LIMIT 1")
            row = cur.fetchone()
            if not row:
                print("❌ Liga 'FIFA World Cup' no encontrada en la BD. Verifica que el schema esté inicializado.")
                return
            league_id = row[0]

        for season in seasons:
            print(f"\n📥 Ingesta del Mundial {season}...")

            # Equipos
            print(f"  Descargando equipos...")
            try:
                teams = self.client.get_competition_teams(WORLD_CUP_CODE, season)
                with self.conn.cursor() as cur:
                    for team in teams:
                        self._upsert_equipo(cur, team)
                self.conn.commit()
                print(f"  ✓ {len(teams)} equipos procesados")
            except Exception as e:
                print(f"  ⚠ Error en equipos: {e}")
                self.conn.rollback()

            time.sleep(6)  # Respetar rate limit: 10 calls/min en plan gratuito

            # Partidos
            print(f"  Descargando partidos...")
            try:
                matches = self.client.get_matches(WORLD_CUP_CODE, season, status="ALL")
                with self.conn.cursor() as cur:
                    for match in matches:
                        self._upsert_partido(cur, match, league_id)
                self.conn.commit()
                completados = sum(1 for m in matches if m.get("status") == "FINISHED")
                proximos = sum(1 for m in matches if m.get("status") in ("SCHEDULED", "TIMED"))
                print(f"  ✓ {len(matches)} partidos: {completados} completados, {proximos} próximos")
            except Exception as e:
                print(f"  ⚠ Error en partidos: {e}")
                self.conn.rollback()

            time.sleep(6)

        print("\n🎉 Ingestión completada.")
        self._mostrar_resumen()

    def _mostrar_resumen(self):
        """Muestra un resumen de los datos cargados."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM teams WHERE country IS NOT NULL")
            n_equipos = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM matches WHERE is_completed = TRUE")
            n_partidos = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM matches WHERE is_completed = FALSE")
            n_proximos = cur.fetchone()[0]

        print(f"\n📊 Resumen de la BD:")
        print(f"   Equipos:           {n_equipos}")
        print(f"   Partidos jugados:  {n_partidos}")
        print(f"   Partidos futuros:  {n_proximos}")

    def close(self):
        self.conn.close()


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Ingestar datos del Mundial FIFA desde football-data.org"
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("FOOTBALL_DATA_API_KEY"),
        help="API key de football-data.org",
    )
    parser.add_argument(
        "--seasons",
        nargs="+",
        type=int,
        default=[2022, 2026],
        help="Temporadas/años del Mundial a descargar (ej: 2018 2022 2026)",
    )
    parser.add_argument(
        "--db-url",
        default=DATABASE_URL,
        help="URL de conexión a PostgreSQL",
    )

    args = parser.parse_args()

    if not args.api_key:
        print("❌ ERROR: Se requiere API key de football-data.org")
        print("   Regístrate gratis en: https://www.football-data.org/client/register")
        print("   Luego ejecuta: python ingest_world_cup.py --api-key TU_KEY")
        exit(1)

    print("=" * 60)
    print("  PREDICTOR FÚTBOL — Ingestión de datos del Mundial FIFA")
    print("=" * 60)
    print(f"  Temporadas: {args.seasons}")
    print(f"  Base de datos: {args.db_url.split('@')[-1]}")
    print()

    ingestador = IngestorMundial(args.db_url, args.api_key)
    try:
        ingestador.ingestar_mundial(args.seasons)
    finally:
        ingestador.close()
