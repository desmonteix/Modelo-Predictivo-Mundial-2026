import psycopg2, os
db_url = os.getenv('DATABASE_URL', 'postgresql://predictor:predictor_pass@localhost:5432/predictor_futbol').replace('postgresql+asyncpg://', 'postgresql://')
conn = psycopg2.connect(db_url)
cur = conn.cursor()
cur.execute("SELECT team_id, name FROM teams WHERE name ILIKE '%Cape%' OR name ILIKE '%Cabo%'")
print('Team:', cur.fetchall())
