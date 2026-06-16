import asyncio
import httpx

async def main():
    async with httpx.AsyncClient() as client:
        res = await client.post("http://predictor_api:8000/api/v1/predict", json={
            "home_team_name": "France",
            "away_team_name": "Senegal",
            "league_name": "FIFA World Cup",
            "match_stage": "Group Stage",
            "is_neutral": True
        })
        print("Status:", res.status_code)
        data = res.json()
        if "predictions" in data:
            print("Goals Home:", data["predictions"]["goals_home"]["value"])
            print("Goals Away:", data["predictions"]["goals_away"]["value"])
            if "exact_scores" in data["predictions"]:
                print("Exact Scores:", data["predictions"]["exact_scores"])
            print(data)

asyncio.run(main())
