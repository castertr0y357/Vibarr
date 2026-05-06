import requests
import logging
from ...models import AppConfig

logger = logging.getLogger(__name__)

class SeerrService:
    def __init__(self, url=None, api_key=None):
        config = AppConfig.objects.first()
        self.base_url = url or (config.seerr_url if config else None)
        self.api_key = api_key or (config.seerr_api_key if config else None)
        self.headers = {
            "X-Api-Key": self.api_key,
            "Content-Type": "application/json"
        }

    def test_connection(self) -> bool:
        if not self.base_url or not self.api_key:
            return False
        try:
            url = f"{self.base_url.rstrip('/')}/api/v1/status"
            response = requests.get(url, headers=self.headers, timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Seerr Connection Error: {e}")
            return False

    def request_media(self, tmdb_id, media_type="tv"):
        """Requests media in Overseerr/Jellyseerr."""
        if not self.base_url or not self.api_key:
            return False
        
        try:
            url = f"{self.base_url.rstrip('/')}/api/v1/request"
            payload = {
                "mediaType": media_type,
                "mediaId": tmdb_id,
            }
            response = requests.post(url, headers=self.headers, json=payload, timeout=10)
            return response.status_code in [200, 201]
        except Exception as e:
            logger.error(f"Seerr Request Error: {e}")
            return False
