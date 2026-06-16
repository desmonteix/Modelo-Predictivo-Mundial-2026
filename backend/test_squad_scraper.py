import httpx
import re

def test_squads():
    url = "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_squads"
    headers = {"User-Agent": "Mozilla/5.0"}
    html = httpx.get(url, headers=headers).text
    
    # Encontrar bloque de tabla después de France
    match = re.search(r'id="France"[^>]*>.*?<table class="sortable[^>]*>(.*?)</table>', html, re.IGNORECASE | re.DOTALL)
    if not match:
        print("France table not found!")
        return
        
    table_html = match.group(1)
    rows = re.findall(r'<tr[^>]*>.*?</tr>', table_html, re.IGNORECASE | re.DOTALL)
    
    total_goals = 0
    for row in rows[1:]: # skip header
        cols = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row, re.IGNORECASE | re.DOTALL)
        if len(cols) >= 6:
            name = re.sub(r'<[^>]+>', '', cols[2]).strip()
            caps = re.sub(r'<[^>]+>', '', cols[4]).strip()
            goals = re.sub(r'<[^>]+>', '', cols[5]).strip()
            print(f"{name}: {caps} caps, {goals} goals")
            try:
                total_goals += int(goals)
            except:
                pass
    print("Total goals:", total_goals)

test_squads()
