import psycopg2, os
db_url = os.getenv('DATABASE_URL', 'postgresql://predictor:predictor_pass@localhost:5432/predictor_futbol').replace('postgresql+asyncpg://', 'postgresql://')
conn = psycopg2.connect(db_url)
cur = conn.cursor()
cur.execute("SELECT team_id, name, external_id FROM teams WHERE name = 'Spain'")
print('Spain teams:', cur.fetchall())

# Delete duplicates keeping the ones that have World Cup matches or the oldest ones
cur.execute("""
WITH duplicate_teams AS (
    SELECT name, MIN(team_id) as keep_id
    FROM teams
    GROUP BY name
    HAVING COUNT(*) > 1
)
SELECT * FROM duplicate_teams;
""")
dups = cur.fetchall()
print("Duplicates to fix:", len(dups))
