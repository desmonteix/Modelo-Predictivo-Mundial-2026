import json
import random
import re
import httpx
from pathlib import Path

CACHE_FILE = Path(__file__).parent.parent / "data" / "player_stats_cache.json"

INITIAL_DB = {
    "spain": {
        "offensive_impact": 1.4,
        "defensive_impact": 1.3,
        "key_attacker": {"name": "Álvaro Morata", "club_goals": 15},
        "key_defender": {"name": "Rodri", "tackles_won_pct": 78.5}
    },
    "cape verde islands": {
        "offensive_impact": 0.3, 
        "defensive_impact": 0.4,
        "key_attacker": {"name": "Bebé", "club_goals": 0},
        "key_defender": {"name": "Roberto Lopes", "tackles_won_pct": 45.2}
    }
}

class PlayerImpactService:
    def __init__(self):
        self._ensure_cache()

    def _ensure_cache(self):
        if not CACHE_FILE.exists():
            CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(INITIAL_DB, f, indent=2, ensure_ascii=False)

    def _load_cache(self) -> dict:
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return INITIAL_DB

    def _save_cache(self, db):
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=2, ensure_ascii=False)

    def scrape_wikipedia_impact(self, team_name: str, elo: float) -> dict:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        total_goals = 0
        top_scorer = {"name": "Desconocido", "goals": 0}
        
        wc_url = "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_squads"
        team_found_in_wc = False
        
        try:
            # 1. Intentar buscar en la página de convocados del Mundial 2026
            resp = httpx.get(wc_url, headers=headers, timeout=5.0, follow_redirects=True)
            if resp.status_code == 200:
                html = resp.text
                wiki_name_id = team_name.replace(" ", "_").title()
                
                # Buscar la tabla del equipo específico
                match = re.search(rf'id="{wiki_name_id}"[^>]*>.*?<table class="sortable[^>]*>(.*?)</table>', html, re.IGNORECASE | re.DOTALL)
                
                # A veces el ID de Wikipedia es ligeramente diferente (ej: United_States en vez de USA)
                if not match and team_name.lower() == "usa":
                    match = re.search(r'id="United_States"[^>]*>.*?<table class="sortable[^>]*>(.*?)</table>', html, re.IGNORECASE | re.DOTALL)
                    
                if match:
                    team_found_in_wc = True
                    table_html = match.group(1)
                    rows = re.findall(r'<tr[^>]*>.*?</tr>', table_html, re.IGNORECASE | re.DOTALL)
                    
                    for row in rows[1:]: # saltar header
                        cols = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row, re.IGNORECASE | re.DOTALL)
                        if len(cols) >= 6:
                            name = re.sub(r'<[^>]+>', '', cols[2]).strip()
                            goals_text = re.sub(r'<[^>]+>', '', cols[5]).strip()
                            goals = int(re.sub(r'\D', '', goals_text)) if re.sub(r'\D', '', goals_text) else 0
                            
                            if goals > 0 and goals < 200:
                                total_goals += goals
                                if goals > top_scorer["goals"]:
                                    top_scorer = {"name": name, "goals": goals}
                                    
            # 2. Fallback a la página de la selección si no está en el Mundial (o falla el regex)
            if not team_found_in_wc:
                wiki_name = team_name.replace(" ", "_").title()
                url = f"https://en.wikipedia.org/wiki/{wiki_name}_national_football_team"
                resp = httpx.get(url, headers=headers, timeout=3.0, follow_redirects=True)
                if resp.status_code == 200:
                    html = resp.text
                    rows = re.findall(r'<tr[^>]*>.*?</tr>', html, re.IGNORECASE | re.DOTALL)
                    for row in rows:
                        cols = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row, re.IGNORECASE | re.DOTALL)
                        if len(cols) >= 5:
                            name_match = re.search(r'<a[^>]*>([^<]+)</a>', cols[1])
                            name = name_match.group(1) if name_match else re.sub(r'<[^>]+>', '', cols[1]).strip()
                            goals_text = re.sub(r'<[^>]+>', '', cols[-2]).strip()
                            goals = int(re.sub(r'\D', '', goals_text)) if re.sub(r'\D', '', goals_text) else 0
                            
                            if goals > 0 and goals < 200:
                                total_goals += goals
                                if goals > top_scorer["goals"]:
                                    top_scorer = {"name": name, "goals": goals}
        except Exception as e:
            print(f"Error scraping player impact: {e}")

        base_impact = max(0.4, min(1.5, elo / 1500.0))
        
        # Si logramos scrapear goles, ajustamos el impacto ofensivo masivamente
        if total_goals > 0:
            if total_goals > 100:
                offensive_impact = 1.35 # Súper letal (Uruguay, Brasil, etc)
            elif total_goals > 50:
                offensive_impact = 1.15
            elif total_goals > 20:
                offensive_impact = 1.0
            else:
                offensive_impact = 0.85
                
            return {
                "offensive_impact": offensive_impact,
                "defensive_impact": base_impact, # Mantenemos ELO para defensa
                "key_attacker": {"name": top_scorer["name"], "club_goals": top_scorer["goals"]},
                "key_defender": {"name": "Pilar defensivo", "tackles_won_pct": 50.0 + (base_impact * 15)},
                "scraped": True
            }
            
        # Fallback al ELO si falla el scraper
        return {
            "offensive_impact": base_impact + random.uniform(-0.05, 0.05),
            "defensive_impact": base_impact + random.uniform(-0.05, 0.05),
            "key_attacker": {"name": "Goleador histórico", "club_goals": int(base_impact * 10)},
            "key_defender": {"name": "Pilar defensivo", "tackles_won_pct": 50.0 + (base_impact * 15)},
            "scraped": False
        }

    def get_team_impact(self, team_name: str, elo: float = 1500.0) -> dict:
        db = self._load_cache()
        key = team_name.lower().strip()
        
        # Búsqueda exacta primero
        for db_key, data in db.items():
            if db_key == key:
                return data

        # Si no está, lo scrapeamos en tiempo real y lo guardamos
        impact_data = self.scrape_wikipedia_impact(team_name, elo)
        
        # Guardamos en caché
        db[key] = impact_data
        self._save_cache(db)
        
        return impact_data

player_impact_service = PlayerImpactService()
