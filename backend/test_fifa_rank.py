import httpx
import re
import html

def get_fifa_rankings():
    url = "https://en.wikipedia.org/wiki/FIFA_Men%27s_World_Ranking"
    headers = {"User-Agent": "Mozilla/5.0"}
    html_text = httpx.get(url, headers=headers).text
    
    match = re.search(r'<table[^>]*class="wikitable[^>]*>.*?</table>', html_text, re.IGNORECASE | re.DOTALL)
    if not match:
        print("No se encontró tabla de ranking")
        return
        
    table_html = match.group(0)
    rows = re.findall(r'<tr[^>]*>.*?</tr>', table_html, re.IGNORECASE | re.DOTALL)
    
    rankings = {}
    for row in rows:
        cols = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row, re.IGNORECASE | re.DOTALL)
        if len(cols) >= 3:
            rank_text = re.sub(r'<[^>]+>', '', cols[0]).strip()
            team_text = re.sub(r'<[^>]+>', '', cols[2]).strip()
            team_text = html.unescape(team_text).strip()
            try:
                rank = int(re.sub(r'\D', '', rank_text))
                if team_text:
                    rankings[team_text] = rank
            except:
                pass
                
    print(f"Total rankings scraped: {len(rankings)}")
    for k, v in list(rankings.items())[:5]:
        print(f"{k}: {v}")
    if "South Africa" in rankings:
        print(f"South Africa: {rankings['South Africa']}")
    else:
        print("South Africa not found in top table.")

get_fifa_rankings()
