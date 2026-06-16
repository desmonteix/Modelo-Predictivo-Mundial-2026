"""
Script para recalcular el ELO histórico de todos los equipos.
"""

import os
import sys
import psycopg2

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from features.elo import construir_sistema_elo, SistemaELO

FIFA_INITIAL_RANKING = {
    "Argentina": 1877.27,
    "France": 1870.70,
    "Spain": 1874.71,
    "England": 1828.02,
    "Brazil": 1765.86,
    "Portugal": 1767.85,
    "Netherlands": 1753.57,
    "Belgium": 1742.24,
    "Italy": 1724.60,
    "Croatia": 1728.30,
    "Uruguay": 1726.33,
    "Morocco": 1755.10,
    "USA": 1681.13,
    "Colombia": 1725.14,
    "Mexico": 1661.11,
    "Germany": 1735.77,
    "Senegal": 1620.74,
    "Japan": 1614.33,
    "Switzerland": 1613.44,
    "Iran": 1608.23,
    "Denmark": 1602.72,
    "Korea Republic": 1563.99,
    "Australia": 1539.22,
    "Wales": 1532.68,
    "Qatar": 1504.06,
    "Ecuador": 1517.54,
    "Poland": 1520.24,
    "Canada": 1461.16,
    "Costa Rica": 1437.57,
    "Cameroon": 1452.59,
    "Saudi Arabia": 1443.53,
    "Ghana": 1416.26,
    "Lithuania": 1100.0,
    "Gibraltar": 850.0
}

def main():
    db_url = os.getenv("DATABASE_URL", "postgresql://predictor:predictor_pass@localhost:5432/predictor_futbol").replace("postgresql+asyncpg://", "postgresql://")
    conn = psycopg2.connect(db_url)
    
    print("Obteniendo todos los partidos completados para recalcular ELO...")
    with conn.cursor() as cur:
        # Extraer partidos en orden cronológico
        cur.execute("""
            SELECT 
                m.home_team_id, m.away_team_id, m.home_goals, m.away_goals,
                l.competition_type as competition, m.is_neutral_venue, m.match_importance
            FROM matches m
            JOIN leagues l ON m.league_id = l.league_id
            WHERE m.is_completed = TRUE
            ORDER BY m.date ASC
        """)
        columns = [desc[0] for desc in cur.description]
        partidos = [dict(zip(columns, row)) for row in cur.fetchall()]
        
    print("Sembrando ELO inicial basado en Ranking FIFA...")
    sistema = SistemaELO()
    with conn.cursor() as cur:
        cur.execute("SELECT team_id, name FROM teams")
        for row in cur.fetchall():
            team_id = row[0]
            name = row[1]
            seed_elo = FIFA_INITIAL_RANKING.get(name, 1400.0)  # 1400 base para no rankeados
            sistema.ratings[team_id] = seed_elo

    print(f"Recalculando ELO sobre {len(partidos)} partidos...")
    sistema = construir_sistema_elo(partidos, sistema=sistema)
    
    print("Guardando el nuevo ELO en la base de datos (team_form)...")
    with conn.cursor() as cur:
        for team_id, elo in sistema.ratings.items():
            # Actualizar o insertar el ELO más reciente en team_form
            cur.execute("""
                INSERT INTO team_form (team_id, as_of_date, league_id, elo_rating)
                VALUES (%s, CURRENT_DATE, 1, %s)
                ON CONFLICT (team_id, as_of_date, league_id) DO UPDATE SET
                    elo_rating = EXCLUDED.elo_rating
            """, (team_id, elo))
            
    conn.commit()
    conn.close()
    
    print("✅ ELO recalculado exitosamente. Top 5 equipos:")
    ranking = sistema.get_ranking(5)
    for t_id, elo in ranking:
        print(f"Team ID: {t_id} | ELO: {elo:.2f}")

if __name__ == "__main__":
    main()
