import httpx
import re

def get_live_rankings():
    url = "https://football-ranking.com/fifa_rankings"
    headers = {"User-Agent": "Mozilla/5.0"}
    html = httpx.get(url, headers=headers).text
    
    # Try with regex first
    rows = re.findall(r'<tr[^>]*>.*?<td[^>]*>(.*?)</td>.*?<td[^>]*>.*?<a[^>]*>(.*?)</a>.*?</td>.*?</tr>', html, re.IGNORECASE | re.DOTALL)
    
    rankings = {}
    for row in rows:
        rank_text = re.sub(r'<[^>]+>', '', row[0]).strip()
        team_text = re.sub(r'<[^>]+>', '', row[1]).strip()
        try:
            rank = int(re.sub(r'\D', '', rank_text))
            rankings[team_text] = rank
        except:
            pass
            
    print(f"Scraped {len(rankings)} from football-ranking.com")
    for k, v in list(rankings.items())[:10]:
        print(f"{k}: {v}")
    if "South Africa" in rankings:
        print(f"South Africa: {rankings['South Africa']}")

get_live_rankings()
