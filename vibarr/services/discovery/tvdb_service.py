import requests
import logging
from django.core.cache import cache
from django.conf import settings
from ...models import AppConfig

logger = logging.getLogger(__name__)

class TVDBService:
    BASE_URL = "https://api4.thetvdb.com/v4"
    _session = None
    
    def __init__(self, api_key=None, pin=None):
        config = AppConfig.get_solo()
        self.api_key = api_key or config.tvdb_api_key
        self.pin = pin or config.tvdb_pin
        
        if TVDBService._session is None:
            TVDBService._session = requests.Session()

    def _get_token(self):
        """Retrieves or refreshes the bearer token."""
        cache_key = f"tvdb_token_{self.api_key}"
        token = cache.get(cache_key)
        
        if not token and self.api_key:
            try:
                url = f"{self.BASE_URL}/login"
                payload = {"apikey": self.api_key}
                if self.pin:
                    payload["pin"] = self.pin
                
                response = self._session.post(url, json=payload, timeout=10)
                response.raise_for_status()
                data = response.json()
                token = data.get("data", {}).get("token")
                
                if token:
                    # Token is valid for 1 month, but we'll cache it for 28 days
                    cache.set(cache_key, token, 60 * 60 * 24 * 28)
            except Exception as e:
                logger.error(f"TVDB Auth Error: {e}")
                return None
                
        return token

    def test_connection(self):
        """Verifies API key and connectivity."""
        if not self.api_key: return False
        token = self._get_token()
        if not token: return False
        
        try:
            url = f"{self.BASE_URL}/countries"
            headers = {"Authorization": f"Bearer {token}"}
            response = self._session.get(url, headers=headers, timeout=5)
            return response.status_code == 200
        except Exception:
            return False

    def _get(self, endpoint, params=None, cache_key=None, ttl=3600):
        if cache_key:
            cached = cache.get(cache_key)
            if cached: return cached

        token = self._get_token()
        if not token: return None

        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        headers = {"Authorization": f"Bearer {token}"}
        
        try:
            response = self._session.get(url, params=params, headers=headers, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            if cache_key:
                cache.set(cache_key, data, ttl)
            return data
        except Exception as e:
            logger.error(f"TVDB API Error [{endpoint}]: {e}")
            return None

    def search_series(self, title):
        """Searches for a series by title."""
        params = {"query": title, "type": "series"}
        cache_key = f"tvdb_search_{title.lower()}"
        data = self._get("search", params=params, cache_key=cache_key)
        results = data.get("data", []) if data else []
        return results[0] if results else None

    def get_series_details(self, tvdb_id):
        """Fetches extended details for a series."""
        cache_key = f"tvdb_series_{tvdb_id}"
        return self._get(f"series/{tvdb_id}/extended", cache_key=cache_key)

    def get_series_by_tmdb_id(self, tmdb_id):
        """Fetches series details using TMDB ID as a reference via search."""
        params = {"remote_id": f"tmdb:{tmdb_id}"}
        cache_key = f"tvdb_remote_tmdb_{tmdb_id}"
        data = self._get("search/remote/tmdb", params=params, cache_key=cache_key)
        results = data.get("data", []) if data else []
        return results[0] if results else None
