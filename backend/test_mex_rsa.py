import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import sys

# We can connect directly to the DB from a script running in the api container
async def main():
    engine = create_async_engine("postgresql+asyncpg://predictor:predictor_pass@postgres:5432/predictor_futbol")
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    
    async with async_session() as db:
        # Get Team IDs
        res = await db.execute(text("SELECT team_id, name FROM teams WHERE name IN ('Mexico', 'South Africa')"))
        teams = {row.name: row.team_id for row in res.fetchall()}
        
        for name, team_id in teams.items():
            print(f"--- {name} ---")
            query = text("""
                SELECT
                    m.date, m.home_team_id, m.away_team_id,
                    m.home_goals, m.away_goals, m.result,
                    COALESCE(s.xg, 0) as xg
                FROM matches m
                LEFT JOIN team_stats_per_match s
                    ON s.match_id = m.match_id AND s.team_id = :team_id
                WHERE (m.home_team_id = :team_id OR m.away_team_id = :team_id)
                  AND m.is_completed = TRUE
                ORDER BY m.date DESC
                LIMIT 10
            """)
            hist = (await db.execute(query, {"team_id": team_id})).fetchall()
            for p in hist:
                es_local = p.home_team_id == team_id
                gf = p.home_goals if es_local else p.away_goals
                gc = p.away_goals if es_local else p.home_goals
                print(f"{p.date.date()} | GF: {gf} GC: {gc} | xG: {p.xg:.2f}")

asyncio.run(main())
