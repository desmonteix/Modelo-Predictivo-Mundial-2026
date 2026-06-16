"""
API Cache Manager para API-Football.
Protege el límite estricto de 100 peticiones/día guardando respuestas en disco.
"""

import os
import json
import time
import hashlib
from datetime import datetime
from pathlib import Path

import httpx

API_BASE = "https://v3.football.api-sports.io"
CACHE_DIR = Path(__file__).parent / ".cache" / "api-football"
QUOTA_FILE = CACHE_DIR / "quota.json"


class ApiFootballClient:
    def __init__(self, api_key: str):
        if not api_key or api_key == "TU_API_KEY_AQUI":
            raise ValueError("API_FOOTBALL_KEY no configurada correctamente.")
            
        self.headers = {
            "x-rapidapi-host": "v3.football.api-sports.io",
            "x-rapidapi-key": api_key,
        }
        self.client = httpx.Client(headers=self.headers, timeout=30.0)
        
        # Ensure cache directory exists
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _get_cache_key(self, endpoint: str, params: dict) -> str:
        """Genera un hash único para la combinación endpoint + params."""
        param_str = json.dumps(params, sort_keys=True)
        key_raw = f"{endpoint}_{param_str}"
        return hashlib.md5(key_raw.encode()).hexdigest()

    def _check_quota(self) -> int:
        """Retorna las peticiones hechas hoy."""
        today = datetime.now().strftime("%Y-%m-%d")
        if QUOTA_FILE.exists():
            with open(QUOTA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data.get("date") == today:
                    return data.get("count", 0)
        return 0

    def _increment_quota(self):
        """Incrementa el contador de peticiones de hoy."""
        today = datetime.now().strftime("%Y-%m-%d")
        count = self._check_quota()
        with open(QUOTA_FILE, "w", encoding="utf-8") as f:
            json.dump({"date": today, "count": count + 1}, f)

    def get(self, endpoint: str, params: dict = None, ignore_cache=False) -> dict:
        """
        Hace una petición GET. Retorna desde caché si existe.
        Respeta el rate limit de 10 peticiones por minuto (esperando si es necesario).
        """
        params = params or {}
        cache_key = self._get_cache_key(endpoint, params)
        cache_file = CACHE_DIR / f"{endpoint.replace('/', '_')}_{cache_key}.json"

        if not ignore_cache and cache_file.exists():
            # Leer desde caché
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)

        # Verificar cuota diaria
        quota_used = self._check_quota()
        if quota_used >= 95:  # Margen de seguridad de 5 peticiones
            print(f"  🚨 ALERTA: Límite diario de API-Football casi alcanzado ({quota_used}/100). Abortando petición.")
            return {}

        # Hacer petición real
        url = f"{API_BASE}/{endpoint.lstrip('/')}"
        print(f"  → GET API-Football: {endpoint} {params}")
        
        try:
            response = self.client.get(url, params=params)
            
            # Rate limiting 10 req/min (para API-Sports el límite suele ser 10 req/min en plan gratis)
            # Siempre esperamos 6.5 segundos para no excederlo
            time.sleep(6.5)
            
            if response.status_code == 429:
                print("  ⚠ Rate limit — esperando 60 segundos...")
                time.sleep(60)
                return self.get(endpoint, params, ignore_cache=False)
                
            response.raise_for_status()
            data = response.json()
            
            # Guardar en caché si la respuesta es válida
            if data.get("errors"):
                print(f"  ⚠ Error en API: {data.get('errors')}")
            else:
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                self._increment_quota()
                print(f"  ✓ Datos guardados en caché. Cuota usada hoy: {quota_used + 1}/100")
                
            return data
            
        except Exception as e:
            print(f"  ❌ Error de conexión: {e}")
            return {}

    def get_fixtures_by_league(self, league_id: int, season: int):
        return self.get("fixtures", {"league": league_id, "season": season})

    def get_fixture_statistics(self, fixture_id: int):
        return self.get("fixtures/statistics", {"fixture": fixture_id})

    def get_fixture_players(self, fixture_id: int):
        return self.get("fixtures/players", {"fixture": fixture_id})

    def get_injuries_by_league(self, league_id: int, season: int):
        return self.get("injuries", {"league": league_id, "season": season})
        
    def get_team_statistics(self, team_id: int, league_id: int, season: int):
        return self.get("teams/statistics", {"team": team_id, "league": league_id, "season": season})

    def print_quota(self):
        quota = self._check_quota()
        print(f"\n📊 Cuota API-Football (Hoy): {quota}/100 requests")
        if quota >= 90:
            print("  ⚠️ ¡Cuidado! Límite diario casi alcanzado.")
