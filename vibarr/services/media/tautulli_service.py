import requests
import logging
from ...models import AppConfig

logger = logging.getLogger(__name__)

class TautulliService:
    def __init__(self):
        from ...models import AppConfig
        config = AppConfig.get_solo()
        self.base_url = config.tautulli_url or ""
        self.api_key = config.tautulli_api_key or ""

    def is_configured(self):
        return bool(self.base_url and self.api_key)

    def get_user_stats(self, username):
        """Example: Fetch more detailed stats for a specific user."""
        if not self.is_configured():
            return None
            
        params = {
            'apikey': self.api_key,
            'cmd': 'get_user_watch_stat',
            'user': username
        }
        try:
            response = requests.get(f"{self.base_url}/api/v2", params=params)
            response.raise_for_status()
            return response.json().get('response', {}).get('data', [])
        except Exception as e:
            logger.error(f"Tautulli Error: {e}")
            return None

    def get_library_user_stats(self):
        """Fetches general watch stats to help AI understand time-of-day habits."""
        if not self.is_configured():
            return None
            
        params = {
            'apikey': self.api_key,
            'cmd': 'get_library_watch_time_stats'
        }
        try:
            response = requests.get(f"{self.base_url}/api/v2", params=params)
            response.raise_for_status()
            return response.json().get('response', {}).get('data', [])
        except Exception as e:
            logger.error(f"Tautulli Error: {e}")
            return None
