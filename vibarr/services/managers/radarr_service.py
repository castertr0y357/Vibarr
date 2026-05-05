import requests
from django.conf import settings

class RadarrService:
    def __init__(self):
        from ...models import AppConfig
        config = AppConfig.get_solo()
        self.base_url = (config.radarr_url or getattr(settings, 'RADARR_URL', '')).rstrip('/')
        self.api_key = config.radarr_api_key or getattr(settings, 'RADARR_API_KEY', '')
        self.headers = {"X-Api-Key": self.api_key}

    def get_root_folders(self):
        if not self.base_url: return []
        url = f"{self.base_url}/api/v3/rootfolder"
        response = requests.get(url, headers=self.headers, timeout=10)
        response.raise_for_status()
        return response.json()

    def get_quality_profiles(self):
        if not self.base_url: return []
        url = f"{self.base_url}/api/v3/qualityprofile"
        response = requests.get(url, headers=self.headers, timeout=10)
        response.raise_for_status()
        return response.json()

    def add_movie(self, tmdb_id, title):
        if not self.base_url: raise Exception("Radarr URL not configured.")
        
        lookup_url = f"{self.base_url}/api/v3/movie/lookup"
        params = {"term": f"tmdb:{tmdb_id}"}
        try:
            lookup_res = requests.get(lookup_url, params=params, headers=self.headers, timeout=15)
            lookup_res.raise_for_status()
            results = lookup_res.json()
            if not results:
                raise Exception(f"No results found in Radarr for TMDB ID {tmdb_id}")
            movie_data = results[0]
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Radarr Lookup Error: {e}")
            raise

        from ...models import AppConfig
        config = AppConfig.get_solo()
        
        # Determine root path
        if config and config.radarr_root_folder:
            root_path = config.radarr_root_folder
        else:
            folders = self.get_root_folders()
            if not folders: raise Exception("No root folders found in Radarr.")
            root_path = folders[0]['path']

        # Determine profile ID
        if config and config.radarr_quality_profile_id:
            profile_id = config.radarr_quality_profile_id
        else:
            profiles = self.get_quality_profiles()
            if not profiles: raise Exception("No quality profiles found in Radarr.")
            profile_id = profiles[0]['id']

        movie_data["rootFolderPath"] = root_path
        movie_data["qualityProfileId"] = profile_id
        movie_data["monitored"] = True
        movie_data["addOptions"] = {"searchForMovie": True}
        
        add_url = f"{self.base_url}/api/v3/movie"
        response = requests.post(add_url, json=movie_data, headers=self.headers, timeout=15)
        response.raise_for_status()
        return response.json()

    def delete_movie(self, movie_id):
        url = f"{self.base_url}/api/v3/movie/{movie_id}"
        params = {"deleteFiles": "true"}
        requests.delete(url, params=params, headers=self.headers).raise_for_status()

    def get_movie(self, movie_id):
        url = f"{self.base_url}/api/v3/movie/{movie_id}"
        response = requests.get(url, headers=self.headers, timeout=10)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()
