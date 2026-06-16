import asyncio, os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from routers.predictions import _predecir_con_datos

async def main():
    db_url = os.getenv('DATABASE_URL', 'postgresql+asyncpg://predictor:predictor_pass@predictor_postgres:5432/predictor_futbol')
    engine = create_async_engine(db_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        # Check ELOs
        cur = await db.execute(text("SELECT team_id, name FROM teams WHERE team_id IN (21, 490)"))
        print(cur.fetchall())
        cur = await db.execute(text("SELECT elo_rating FROM team_form WHERE team_id = 21 ORDER BY as_of_date DESC LIMIT 1"))
        print("Spain ELO:", cur.fetchone())
        cur = await db.execute(text("SELECT elo_rating FROM team_form WHERE team_id = 490 ORDER BY as_of_date DESC LIMIT 1"))
        print("Cape Verde ELO:", cur.fetchone())

        res = await _predecir_con_datos(
            home_team_id=21, away_team_id=490, 
            home_team_name='Spain', away_team_name='Cape Verde Islands', 
            league='World Cup', match_stage='Group Stage', is_neutral=True, db=db)
        

asyncio.run(main())
