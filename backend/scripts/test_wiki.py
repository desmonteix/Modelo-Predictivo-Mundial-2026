import httpx
from bs4 import BeautifulSoup
import re

def scrape_wikipedia_squad(team_name):
    # Format team name for Wikipedia
    wiki_name = team_name.replace(" ", "_").title()
    url = f"https://en.wikipedia.org/wiki/{wiki_name}_national_football_team"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        response = httpx.get(url, headers=headers, timeout=5.0, follow_redirects=True)
        if response.status_code != 200:
            return None
            
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find the "Current squad" section
        squad_span = soup.find(id=re.compile("Current_squad|Squad", re.I))
        if not squad_span:
            return None
            
        # Find the next table (which is usually the squad table)
        table = squad_span.find_next("table", class_="sortable")
        if not table:
            return None
            
        players = []
        rows = table.find_all("tr")[1:] # Skip header
        for row in rows:
            cols = row.find_all(["td", "th"])
            if len(cols) >= 5:
                # Typically: Pos, Player, Date of birth, Caps, Goals, Club
                try:
                    # Player name is usually the second or third column, often a link
                    a_tag = cols[1].find("a")
                    if a_tag:
                        name = a_tag.text
                    else:
                        name = cols[1].text.strip()
                        
                    caps_text = cols[3].text.strip()
                    goals_text = cols[4].text.strip()
                    
                    caps = int(re.sub(r'\D', '', caps_text)) if re.sub(r'\D', '', caps_text) else 0
                    goals = int(re.sub(r'\D', '', goals_text)) if re.sub(r'\D', '', goals_text) else 0
                    
                    players.append({"name": name, "caps": caps, "goals": goals})
                except Exception as e:
                    continue
                    
        return players
    except Exception as e:
        print("Error:", e)
        return None

if __name__ == "__main__":
    squad = scrape_wikipedia_squad("Uruguay")
    if squad:
        print(f"Found {len(squad)} players for Uruguay.")
        for p in squad[:5]:
            print(p)
    else:
        print("Failed to scrape Uruguay")
