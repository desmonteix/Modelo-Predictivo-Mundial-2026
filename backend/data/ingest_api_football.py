"""
Script de Ingestión de Estadísticas Avanzadas (API-Football)
Obtiene estadísticas por partido (xG, posesión) y lesiones, respetando límites diarios.

Uso:
  python data/ingest_api_football.py --api-key TU_KEY --season 2022
"""

import argparse
import os
import sys

# Agregar la raíz del backend al path para poder importar módulos
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.api_cache import ApiFootballClient
from db.repositories import IngestionRepository

# Ligas principales para un dataset robusto (Mundiales, Continental, Clasificatorias)
COMPETITIONS_TO_INGEST = [
    {"id": 1, "name": "World Cup"},
    {"id": 4, "name": "Euro Championship"},
    {"id": 9, "name": "Copa America"},
    {"id": 5, "name": "UEFA Nations League"},
    {"id": 32, "name": "World Cup Qualification - UEFA"},
    {"id": 34, "name": "World Cup Qualification - CONMEBOL"},
    {"id": 33, "name": "World Cup Qualification - CONCACAF"},
    {"id": 10, "name": "Friendlies"}
]

def process_league(client, repo, league_id: int, league_name: str, season: int, fetch_players: bool):
    print(f"\n" + "="*50)
    print(f" Procesando: {league_name} ({season})")
    print("="*50)
    print("=" * 60)
    print(f"  PREDICTOR FÚTBOL — Ingestión API-Football (Mundial {season})")
    print("=" * 60)

    # 1. Obtener Fixtures de API-Football
    print(f"📥 Descargando calendario para {league_name}...")
    fixtures_data = client.get_fixtures_by_league(league_id, season)
    if not fixtures_data:
        return

    fixtures = fixtures_data.get("response", [])
    print(f"  ✓ {len(fixtures)} partidos encontrados.")

    # 2. Descargar Estadísticas por Partido
    print("📥 Descargando estadísticas avanzadas (xG, posesión, tiros)...")
    stats_procesadas = 0
    
    for f in fixtures:
        fix_id = f["fixture"]["id"]
        status = f["fixture"]["status"]["short"]
        
        if status not in ["FT", "PEN", "AET"]:
            continue
            
        date_str = f["fixture"]["date"]
        home_name = f["teams"]["home"]["name"]
        away_name = f["teams"]["away"]["name"]
        home_api_id = f["teams"]["home"]["id"]
        away_api_id = f["teams"]["away"]["id"]
        
        # Guardar en BD (equipos y partido)
        home_internal_id = repo.upsert_team(home_api_id, home_name)
        away_internal_id = repo.upsert_team(away_api_id, away_name)
        
        home_goals = f["goals"]["home"]
        away_goals = f["goals"]["away"]
        stage = f["league"].get("round", "Group Stage")
        
        match_internal_id = repo.upsert_match(
            api_id=fix_id, date_str=date_str, season=str(season), 
            league_id=league_id, home_id=home_internal_id, away_id=away_internal_id, 
            home_goals=home_goals, away_goals=away_goals, status=status, stage=stage
        )
        repo.commit()

        stats_data = client.get_fixture_statistics(fix_id)
        if not stats_data or not stats_data.get("response"):
            continue
            
        for team_stats in stats_data["response"]:
            team_api_id = team_stats["team"]["id"]
            is_home = (team_api_id == f["teams"]["home"]["id"])
            internal_team_id = home_internal_id if is_home else away_internal_id
            
            flat_stats = {}
            for stat in team_stats["statistics"]:
                val = stat["value"]
                if val is not None:
                    if isinstance(val, str) and "%" in val:
                        val = float(val.replace("%", ""))
                    flat_stats[stat["type"]] = val
            
            repo.upsert_team_stats(match_internal_id, internal_team_id, is_home, flat_stats)
        
        stats_procesadas += 1
        repo.commit()
        
    print(f"  ✓ {stats_procesadas} partidos enriquecidos con estadísticas avanzadas de equipo.")

    # 3. Descargar Estadísticas Individuales de Jugadores (Opcional por cuota)
    if fetch_players:
        print("📥 Descargando estadísticas individuales de jugadores...")
        players_procesados = 0
        for f in fixtures:
            fix_id = f["fixture"]["id"]
            status = f["fixture"]["status"]["short"]
            if status not in ["FT", "PEN", "AET"]:
                continue
                
            date_str = f["fixture"]["date"]
            home_name = f["teams"]["home"]["name"]
            away_name = f["teams"]["away"]["name"]
            
            home_internal_id = repo.get_internal_team_id_by_name(home_name)
            away_internal_id = repo.get_internal_team_id_by_name(away_name)
            match_internal_id = repo.get_internal_match_id(date_str, home_internal_id, away_internal_id)
            if not match_internal_id:
                continue

            players_data = client.get_fixture_players(fix_id)
            if not players_data or not players_data.get("response"):
                continue
                
            for team_data in players_data["response"]:
                team_api_id = team_data["team"]["id"]
                internal_team_id = home_internal_id if team_api_id == f["teams"]["home"]["id"] else away_internal_id
                
                for player_entry in team_data["players"]:
                    p_info = player_entry["player"]
                    # API-Football retorna stats en un array, usualmente 1 item por partido
                    p_stats = player_entry["statistics"][0] if player_entry.get("statistics") else {}
                    
                    repo.upsert_player_stats(
                        match_id=match_internal_id,
                        team_id=internal_team_id,
                        player_id=p_info["id"],
                        player_name=p_info["name"],
                        stats=p_stats
                    )
            players_procesados += 1
            repo.commit()
            
        print(f"  ✓ {players_procesados} partidos con estadísticas individuales de jugadores.")
    else:
        print("⏭️ Saltando descarga de stats individuales de jugadores para proteger la cuota API.")

    # 3. Descargar Lesiones (Injuries) para la competición
    print("📥 Descargando reporte de lesiones actuales...")
    injuries_data = client.get_injuries_by_league(league_id, season)
    
    if injuries_data and injuries_data.get("response"):
        print(f"  ✓ Obtenidas {len(injuries_data['response'])} incidencias de lesiones.")

def main(api_key: str, season: int, db_url: str, fetch_players: bool):
    print("=" * 60)
    print(f"  PREDICTOR FÚTBOL — Ingestión Masiva API-Football ({season})")
    print("=" * 60)

    client = ApiFootballClient(api_key)
    repo = IngestionRepository(db_url)

    try:
        for comp in COMPETITIONS_TO_INGEST:
            process_league(client, repo, comp["id"], comp["name"], season, fetch_players)

    finally:
        repo.close()
        client.print_quota()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingesta desde API-Football")
    parser.add_argument("--api-key", default=os.getenv("API_FOOTBALL_KEY"), help="X-RapidAPI-Key para API-Football")
    parser.add_argument("--season", type=int, default=2022, help="Temporada (ej: 2022)")
    parser.add_argument("--db-url", default=os.getenv("DATABASE_URL", "postgresql://predictor:predictor_pass@localhost:5432/predictor_futbol").replace("postgresql+asyncpg://", "postgresql://"))
    parser.add_argument("--fetch-players", action="store_true", help="Descargar stats individuales (Consume mucha cuota)")
    
    args = parser.parse_args()
    
    if not args.api_key or args.api_key == "TU_API_KEY_AQUI":
        print("❌ Error: Necesitas configurar API_FOOTBALL_KEY en .env")
        exit(1)
        
    main(args.api_key, args.season, args.db_url, args.fetch_players)
