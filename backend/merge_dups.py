import os
import psycopg2

db_url = os.getenv('DATABASE_URL', 'postgresql://predictor:predictor_pass@localhost:5432/predictor_futbol').replace('postgresql+asyncpg://', 'postgresql://')
conn = psycopg2.connect(db_url)
cur = conn.cursor()

print("Merging duplicate teams...")

cur.execute("""
WITH duplicate_teams AS (
    SELECT name, MIN(team_id) as keep_id
    FROM teams
    GROUP BY name
    HAVING COUNT(*) > 1
)
SELECT t.team_id, t.name, d.keep_id
FROM teams t
JOIN duplicate_teams d ON t.name = d.name
WHERE t.team_id != d.keep_id;
""")
dups = cur.fetchall()

if not dups:
    print("No duplicates found.")
else:
    for dup_id, name, keep_id in dups:
        print(f"Merging '{name}' (ID: {dup_id}) into (ID: {keep_id})")
        # Update matches
        cur.execute("UPDATE matches SET home_team_id = %s WHERE home_team_id = %s", (keep_id, dup_id))
        cur.execute("UPDATE matches SET away_team_id = %s WHERE away_team_id = %s", (keep_id, dup_id))
        # Update team_form
        cur.execute("DELETE FROM team_form WHERE team_id = %s", (dup_id,))
        # Update team_stats_per_match
        cur.execute("UPDATE team_stats_per_match SET team_id = %s WHERE team_id = %s AND NOT EXISTS (SELECT 1 FROM team_stats_per_match t2 WHERE t2.match_id = team_stats_per_match.match_id AND t2.team_id = %s)", (keep_id, dup_id, keep_id))
        cur.execute("DELETE FROM team_stats_per_match WHERE team_id = %s", (dup_id,))
        # Delete team
        cur.execute("DELETE FROM teams WHERE team_id = %s", (dup_id,))

conn.commit()
conn.close()
print("Done.")
