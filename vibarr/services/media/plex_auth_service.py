import requests
import uuid

class PlexAuthService:
    BASE_URL = "https://plex.tv/api/v2"
    
    def __init__(self):
        from ...models import AppConfig
        config = AppConfig.get_solo()
        
        # We need a persistent identifier for Plex Auth to work correctly.
        # We derive a stable ID from the app's secret key.
        import hashlib
        from django.conf import settings
        client_id = hashlib.sha256(settings.SECRET_KEY.encode()).hexdigest()[:32]

        self.headers = {
            "X-Plex-Product": "Vibarr",
            "X-Plex-Client-Identifier": client_id,
            "X-Plex-Device": "Web Dashboard",
            "X-Plex-Version": "1.0",
            "Accept": "application/json",
        }

    def get_pin(self):
        url = f"{self.BASE_URL}/pins"
        # We want a strong PIN for modern Plex Auth flows
        payload = {"strong": "true"}
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

    def get_resources(self, token):
        """Fetches all Plex servers associated with the token."""
        try:
            from plexapi.myplex import MyPlexAccount
            import requests
            
            # Use a session that ignores SSL for local discovery if needed
            session = requests.Session()
            session.verify = False
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            account = MyPlexAccount(token=token, session=session)
            resources = account.resources()
            
            servers = []
            for r in resources:
                if r.provides == 'server':
                    # Get the best connection (prefer local)
                    connections = r.connections
                    best_url = ""
                    for c in connections:
                        if c.local:
                            best_url = c.uri
                            break
                    if not best_url and connections:
                        best_url = connections[0].uri
                    
                    servers.append({
                        'name': r.name,
                        'url': best_url,
                        'product': r.product,
                        'owned': r.owned
                    })
            return servers
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Plex Resource Discovery Error: {e}")
            return []
