import httpx
import json
from pathlib import Path
from datetime import datetime, timedelta

CACHE_FILE = Path("data/fifa_rankings_cache.json")
CACHE_DURATION_DAYS = 15

class FIFARankingService:
    def __init__(self):
        self.rankings = {}
        self.last_update = None
        self._load_cache()

    def _load_cache(self):
        if CACHE_FILE.exists():
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.rankings = data.get("rankings", {})
                    self.last_update = datetime.fromisoformat(data.get("last_update", "2000-01-01T00:00:00"))
            except Exception as e:
                print(f"Error cargando caché FIFA: {e}")

    def _save_cache(self):
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "last_update": datetime.now().isoformat(),
                "rankings": self.rankings
            }, f, ensure_ascii=False, indent=2)

    def _fetch_from_api(self):
        """Descarga el ranking actual de la API interna de FIFA"""
        print("Descargando Ranking FIFA Oficial...")
        url = "https://inside.fifa.com/api/ranking-overview?locale=en&dateId=id14338"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        try:
            response = httpx.get(url, headers=headers, timeout=10.0)
            response.raise_for_status()
            data = response.json()
            
            new_rankings = {}
            for item in data.get("rankings", []):
                info = item.get("rankingItem", {})
                name = info.get("name")
                rank = info.get("rank")
                pts = info.get("totalPoints")
                if name and rank and pts:
                    # Normalizar nombres comunes para que coincidan con nuestra BD
                    name_map = {
                        "USA": "United States",
                        "Korea Republic": "South Korea",
                        "IR Iran": "Iran",
                        "Côte d'Ivoire": "Ivory Coast"
                    }
                    norm_name = name_map.get(name, name)
                    new_rankings[norm_name] = {
                        "rank": rank,
                        "points": pts
                    }
            
            if new_rankings:
                self.rankings = new_rankings
                self.last_update = datetime.now()
                self._save_cache()
                print(f"Ranking FIFA actualizado exitosamente ({len(new_rankings)} equipos).")
        except Exception as e:
            print(f"Error descargando ranking FIFA: {e}")

    def get_team_ranking(self, team_name: str) -> dict:
        """
        Retorna el ranking y puntos de un equipo.
        Si la caché expiró o no existe, descarga de la API.
        """
        if not self.rankings or not self.last_update or (datetime.now() - self.last_update) > timedelta(days=CACHE_DURATION_DAYS):
            self._fetch_from_api()
            
        # Intentar coincidencia exacta
        res = self.rankings.get(team_name)
        if res:
            return res
            
        # Intentar coincidencia parcial (ej. "Mexico" en "Mexico")
        for k, v in self.rankings.items():
            if team_name.lower() in k.lower() or k.lower() in team_name.lower():
                return v
                
        # Fallback genérico si no se encuentra (asumir equipo promedio-bajo)
        return {"rank": 80, "points": 1300.0}

fifa_ranking_service = FIFARankingService()
