import requests
import logging
from django.core.cache import cache
from django.conf import settings
from ...models import AppConfig

logger = logging.getLogger(__name__)

class TraktService:
    BASE_URL = "https://api.trakt.tv"

    def __init__(self, client_id=None):
        config = AppConfig.objects.first()
        self.client_id = client_id or (config.trakt_client_id if config else None)
        self.headers = {
            "Content-Type": "application/json",
            "trakt-api-version": "2",
            "trakt-api-key": self.client_id
        }

    def test_connection(self) -> bool:
        """Tests connection to Trakt by fetching trending movies (limit 1)."""
        if getattr(settings, 'MOCK_MODE', False):
            return True
        if not self.client_id:
            return False
        try:
            url = f"{self.BASE_URL}/movies/trending"
            params = {"limit": 1}
            response = requests.get(url, headers=self.headers, params=params, timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Trakt Integration - Error - Connection failed: {e}")
            return False

    def _get_trakt_id(self, tmdb_id: int, media_type: str = "movie") -> int:
        """Resolves a TMDB ID to a Trakt ID using caching."""
        if getattr(settings, 'MOCK_MODE', False):
            return 12345
        if not self.client_id or not tmdb_id:
            return None

        cache_key = f"trakt_id_resolve_{media_type}_{tmdb_id}"
        cached_id = cache.get(cache_key)
        if cached_id:
            return cached_id

        try:
            url = f"{self.BASE_URL}/search/tmdb/{tmdb_id}"
            params = {"type": media_type}
            response = requests.get(url, headers=self.headers, params=params, timeout=5)
            if response.status_code == 200:
                results = response.json()
                if results:
                    item_key = "movie" if media_type == "movie" else "show"
                    trakt_id = results[0].get(item_key, {}).get("ids", {}).get("trakt")
                    if trakt_id:
                        cache.set(cache_key, trakt_id, 86400 * 7) # Cache for 7 days
                        return trakt_id
            return None
        except Exception as e:
            logger.error(f"Trakt Integration - Error - Failed to resolve TMDB ID {tmdb_id}: {e}")
            return None

    def get_related_movies(self, tmdb_id: int) -> list:
        """Fetches related movies for a given TMDB ID."""
        trakt_id = self._get_trakt_id(tmdb_id, "movie")
        if not trakt_id:
            return []

        try:
            url = f"{self.BASE_URL}/movies/{trakt_id}/related"
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                return response.json()
            return []
        except Exception as e:
            logger.error(f"Trakt Integration - Error - Failed to fetch related movies for TMDB ID {tmdb_id}: {e}")
            return []

    def get_related_shows(self, tmdb_id: int) -> list:
        """Fetches related TV shows for a given TMDB ID."""
        trakt_id = self._get_trakt_id(tmdb_id, "show")
        if not trakt_id:
            return []

        try:
            url = f"{self.BASE_URL}/shows/{trakt_id}/related"
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                return response.json()
            return []
        except Exception as e:
            logger.error(f"Trakt Integration - Error - Failed to fetch related shows for TMDB ID {tmdb_id}: {e}")
            return []

    def get_user_history(self, username: str, limit: int = 100) -> list:
        """Fetches public history for a Trakt user."""
        if getattr(settings, 'MOCK_MODE', False):
            return [
                {
                    "id": 101,
                    "type": "movie",
                    "watched_at": "2026-06-02T16:14:39.000Z",
                    "movie": {
                        "title": "Inception",
                        "ids": {"tmdb": 27205, "trakt": 16}
                    }
                },
                {
                    "id": 102,
                    "type": "episode",
                    "watched_at": "2026-06-03T16:14:39.000Z",
                    "show": {
                        "title": "Breaking Bad",
                        "ids": {"tmdb": 1396, "trakt": 3}
                    },
                    "episode": {
                        "season": 1,
                        "number": 1
                    }
                }
            ]
        if not self.client_id or not username:
            return []

        try:
            url = f"{self.BASE_URL}/users/{username}/history"
            params = {"limit": limit}
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Trakt Integration - Warning - Failed to fetch history for '{username}'. Status: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Trakt Integration - Error - Failed to fetch history for '{username}': {e}")
            return []

    def get_user_watchlist(self, username: str) -> list:
        """Fetches public watchlist for a Trakt user."""
        if getattr(settings, 'MOCK_MODE', False):
            return [
                {
                    "id": 201,
                    "type": "show",
                    "show": {
                        "title": "The Bear",
                        "ids": {"tmdb": 136315, "trakt": 1}
                    }
                }
            ]
        if not self.client_id or not username:
            return []

        try:
            url = f"{self.BASE_URL}/users/{username}/watchlist"
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Trakt Integration - Warning - Failed to fetch watchlist for '{username}'. Status: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Trakt Integration - Error - Failed to fetch watchlist for '{username}': {e}")
            return []
