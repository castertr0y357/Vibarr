import requests
import uuid

class PlexAuthService:
    BASE_URL = "https://plex.tv/api/v2"
    
    def __init__(self):
        from ...models import AppConfig
        config = AppConfig.get_solo()
        
        # We need a persistent identifier for Plex Auth to work correctly
        # If we don't have one, we generate it once and save it.
        # However, AppConfig doesn't have a client_id field yet. 
        # For simplicity, we can use a hardcoded one for the app or add it to AppConfig.
        # Let's add it to AppConfig to be proper.
        client_id = getattr(config, 'plex_client_id', None)
        if not client_id:
            client_id = str(uuid.uuid4())
            # We'll assume we add this field or just use a stable one derived from SECRET_KEY
            # Actually, let's just use a hash of the SECRET_KEY for now to avoid migration overhead,
            # or better, just use a stable UUID.
            pass

        self.headers = {
            "X-Plex-Product": "Vibarr",
            "X-Plex-Client-Identifier": "vibarr-unique-client-id-12345", # Stable ID
            "X-Plex-Device": "Web Dashboard",
            "X-Plex-Version": "1.0",
            "Accept": "application/json",
        }

    def get_pin(self):
        url = f"{self.BASE_URL}/pins"
        # We want a standard 4-digit PIN for plex.tv/link
        payload = {"strong": "false"}
        response = requests.post(url, data=payload, headers=self.headers)
        response.raise_for_status()
        try:
            pin_data = response.json()
            import logging
            logging.getLogger(__name__).info(f"Plex PIN Response: {pin_data}")
            return pin_data # Contains 'id' and 'code'
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Plex Auth JSON Error: {e}. Content: {response.text}")
            raise

    def check_pin(self, pin_id):
        url = f"{self.BASE_URL}/pins/{pin_id}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        try:
            data = response.json()
            return data.get('authToken') # Returns None if not yet authorized
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Plex PIN Poll JSON Error: {e}. Content: {response.text}")
            return None
