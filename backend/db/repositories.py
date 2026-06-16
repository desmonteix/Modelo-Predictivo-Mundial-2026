"""
Repositorios para acceso a la base de datos PostgreSQL.
Usa SQLAlchemy con motor síncrono para scripts de ingestión.
"""

from typing import Dict, Any, List
import psycopg2
from psycopg2.extras import Json

class IngestionRepository:
    def __init__(self, db_url: str):
        self.conn = psycopg2.connect(db_url)
        
    def close(self):
        self.conn.close()
        
    def commit(self):
        self.conn.commit()
        
    def rollback(self):
        self.conn.rollback()

    def upsert_team(self, api_id: int, name: str, country: str = "") -> int:
        """Inserta o actualiza un equipo, retorna team_id interno."""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO teams (name, short_name, country, external_id)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (external_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    updated_at = NOW()
                RETURNING team_id
            """, (name, name[:3].upper(), country, str(api_id)))
            row = cur.fetchone()
            if row: return row[0]
            
            cur.execute("SELECT team_id FROM teams WHERE external_id = %s", (str(api_id),))
            return cur.fetchone()[0]

    def upsert_league(self, api_id: int, name: str, country: str = "") -> int:
        """Inserta o actualiza una liga, retorna league_id interno."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT league_id FROM leagues WHERE external_id = %s", (str(api_id),))
            row = cur.fetchone()
            if row:
                cur.execute("UPDATE leagues SET name = %s, country = %s WHERE league_id = %s", (name, country, row[0]))
                return row[0]
            
            cur.execute("""
                INSERT INTO leagues (name, country, external_id)
                VALUES (%s, %s, %s)
                RETURNING league_id
            """, (name, country, str(api_id)))
            return cur.fetchone()[0]

    def upsert_match(self, api_id: int, date_str: str, season: str, league_id: int, 
                     home_id: int, away_id: int, home_goals: int, away_goals: int,
                     status: str, stage: str = "Group Stage", importance: float = 0.8):
        """Inserta o actualiza un partido, retorna match_id interno."""
        is_completed = status in ["FT", "AET", "PEN"]
        result = "H" if (home_goals or 0) > (away_goals or 0) else "A" if (away_goals or 0) > (home_goals or 0) else "D"
        if not is_completed: result = None
        
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO matches (
                    external_id, date, season, league_id,
                    home_team_id, away_team_id, home_goals, away_goals,
                    result, match_stage, match_importance, is_completed, data_source
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (external_id) DO UPDATE SET
                    home_goals = EXCLUDED.home_goals,
                    away_goals = EXCLUDED.away_goals,
                    result = EXCLUDED.result,
                    match_importance = EXCLUDED.match_importance,
                    is_completed = EXCLUDED.is_completed,
                    updated_at = NOW()
                RETURNING match_id
            """, (str(api_id), date_str, str(season), league_id, 
                  home_id, away_id, home_goals, away_goals, 
                  result, stage, importance, is_completed, "api-football"))
            row = cur.fetchone()
            if row: return row[0]
            
            cur.execute("SELECT match_id FROM matches WHERE external_id = %s", (str(api_id),))
            return cur.fetchone()[0]

    def get_internal_team_id_by_name(self, team_name: str) -> int:
        """Busca el ID interno de un equipo por nombre o alias."""
        with self.conn.cursor() as cur:
            # Primero intento directo
            cur.execute("SELECT team_id FROM teams WHERE name ILIKE %s OR short_name ILIKE %s", (team_name, team_name))
            row = cur.fetchone()
            if row:
                return row[0]
                
            # Luego intento con trigramas (fuzzy matching si es soportado, o ILIKE %...%)
            cur.execute("SELECT team_id FROM teams WHERE name ILIKE %s LIMIT 1", (f"%{team_name}%",))
            row = cur.fetchone()
            return row[0] if row else None

    def get_internal_match_id(self, date_str: str, home_team_id: int, away_team_id: int) -> int:
        """Busca un partido por equipos y fecha aproximada."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT match_id 
                FROM matches 
                WHERE home_team_id = %s AND away_team_id = %s 
                AND date::date = %s::date
            """, (home_team_id, away_team_id, date_str))
            row = cur.fetchone()
            return row[0] if row else None

    def upsert_team_stats(self, match_id: int, team_id: int, is_home: bool, stats: Dict[str, Any]):
        """Inserta o actualiza las estadísticas avanzadas de un equipo en un partido."""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO team_stats_per_match (
                    match_id, team_id, is_home,
                    xg, shots, shots_on_target, possession, passes_completed, pass_accuracy,
                    yellow_cards, red_cards, offsides, fouls_committed, corners_for
                ) VALUES (
                    %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s
                )
                ON CONFLICT (match_id, team_id) DO UPDATE SET
                    xg = EXCLUDED.xg,
                    shots = EXCLUDED.shots,
                    shots_on_target = EXCLUDED.shots_on_target,
                    possession = EXCLUDED.possession,
                    passes_completed = EXCLUDED.passes_completed,
                    pass_accuracy = EXCLUDED.pass_accuracy,
                    yellow_cards = EXCLUDED.yellow_cards,
                    red_cards = EXCLUDED.red_cards,
                    offsides = EXCLUDED.offsides,
                    fouls_committed = EXCLUDED.fouls_committed,
                    corners_for = EXCLUDED.corners_for
            """, (
                match_id, team_id, is_home,
                stats.get("expected_goals"),
                stats.get("Total Shots"),
                stats.get("Shots on Goal"),
                stats.get("Ball Possession"),
                stats.get("Total passes"),
                stats.get("Passes %"),
                stats.get("Yellow Cards"),
                stats.get("Red Cards"),
                stats.get("Offsides"),
                stats.get("Fouls"),
                stats.get("Corner Kicks")
            ))

    def upsert_player_availability(self, match_id: int, team_id: int, injuries: List[Dict]):
        """Actualiza el reporte de bajas de un equipo para un partido."""
        
        # Calcular impacto estimado (muy simplificado, en un sistema real depende del jugador)
        impact = min(len(injuries) * 0.1, 1.0)
        
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO players_availability (
                    team_id, match_id, key_players_out, injury_impact_score, updated_at
                ) VALUES (%s, %s, %s, %s, NOW())
                ON CONFLICT (team_id, match_id) DO UPDATE SET
                    key_players_out = EXCLUDED.key_players_out,
                    injury_impact_score = EXCLUDED.injury_impact_score,
                    updated_at = NOW()
            """, (
                team_id, match_id, Json(injuries), impact
            ))

    def upsert_player_stats(self, match_id: int, team_id: int, player_id: int, player_name: str, stats: Dict[str, Any]):
        """Inserta o actualiza estadísticas individuales de un jugador en un partido."""
        
        minutes = stats.get("games", {}).get("minutes") or 0
        if minutes == 0:
            return # No jugó
            
        rating_str = stats.get("games", {}).get("rating")
        rating = float(rating_str) if rating_str else None
        
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO player_stats_per_match (
                    match_id, team_id, player_id, player_name, position,
                    rating, minutes_played, goals, assists, shots,
                    passes_accuracy, tackles, interceptions
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (match_id, player_id) DO UPDATE SET
                    rating = EXCLUDED.rating,
                    minutes_played = EXCLUDED.minutes_played,
                    goals = EXCLUDED.goals,
                    assists = EXCLUDED.assists,
                    shots = EXCLUDED.shots,
                    passes_accuracy = EXCLUDED.passes_accuracy,
                    tackles = EXCLUDED.tackles,
                    interceptions = EXCLUDED.interceptions
            """, (
                match_id, team_id, player_id, player_name,
                stats.get("games", {}).get("position"),
                rating, minutes,
                stats.get("goals", {}).get("total") or 0,
                stats.get("goals", {}).get("assists") or 0,
                stats.get("shots", {}).get("total") or 0,
                stats.get("passes", {}).get("accuracy") or 0,
                stats.get("tackles", {}).get("total") or 0,
                stats.get("tackles", {}).get("interceptions") or 0
            ))
