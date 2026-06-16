import asyncio, os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from routers.predictions import _predecir_con_datos

async def main():
    db_url = os.getenv('DATABASE_URL', 'postgresql+asyncpg://predictor:predictor_pass@predictor_postgres:5432/predictor_futbol')
    engine = create_async_engine(db_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        res = await _predecir_con_datos(
            home_team_id=21, away_team_id=490, 
            home_team_name='Spain', away_team_name='Cape Verde Islands', 
            league='World Cup', match_stage='Group Stage', is_neutral=True, db=db)
        
        print("Goals:", res.predictions.goals_home.value, "vs", res.predictions.goals_away.value)
        print("Probabilities:", res.predictions.result_1X2.home_win_prob, res.predictions.result_1X2.draw_prob, res.predictions.result_1X2.away_win_prob)
        print("Is Fallback?", "fallback" in res.warnings[0] if res.warnings else False)

asyncio.run(main())
