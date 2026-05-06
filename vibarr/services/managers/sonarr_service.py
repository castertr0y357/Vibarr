import requests
from django.conf import settings

class SonarrService:
    def __init__(self, url=None, api_key=None):
        if url and api_key:
            self.base_url = url.rstrip('/')
            self.api_key = api_key
        else:
            from ...models import AppConfig
            config = AppConfig.get_solo()
            self.base_url = (config.sonarr_url or getattr(settings, 'SONARR_URL', '')).rstrip('/')
            self.api_key = config.sonarr_api_key or getattr(settings, 'SONARR_API_KEY', '')
        
        self.headers = {"X-Api-Key": self.api_key}

    def get_root_folders(self):
        url = f"{self.base_url}/api/v3/rootfolder"
        response = requests.get(url, headers=self.headers, timeout=10)
        response.raise_for_status()
        return response.json()

    def get_quality_profiles(self):
        url = f"{self.base_url}/api/v3/qualityprofile"
        response = requests.get(url, headers=self.headers, timeout=10)
        response.raise_for_status()
        return response.json()

    def add_series(self, tmdb_id, title, tasting_count=3):
        # First, lookup the series in Sonarr to get details for adding
        lookup_url = f"{self.base_url}/api/v3/series/lookup"
        params = {"term": f"tmdb:{tmdb_id}"}
        try:
            lookup_res = requests.get(lookup_url, params=params, headers=self.headers, timeout=15)
            lookup_res.raise_for_status()
            results = lookup_res.json()
            if not results:
                raise Exception(f"No results found in Sonarr for TMDB ID {tmdb_id}")
            series_data = results[0]
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Sonarr Lookup Error: {e}")
            raise

        from ...models import AppConfig
        config = AppConfig.get_solo()
        
        # Use saved config or defaults
        if not config or not config.sonarr_root_folder:
            folders = self.get_root_folders()
            if not folders:
                raise Exception("No root folders found in Sonarr and none configured.")
            root_path = folders[0]['path']
        else:
            root_path = config.sonarr_root_folder

        if not config or not config.sonarr_quality_profile_id:
            profiles = self.get_quality_profiles()
            if not profiles:
                raise Exception("No quality profiles found in Sonarr and none configured.")
            profile_id = profiles[0]['id']
        else:
            profile_id = config.sonarr_quality_profile_id

        series_data["rootFolderPath"] = root_path
        series_data["qualityProfileId"] = profile_id
        series_data["monitored"] = True
        series_data["addOptions"] = {"searchForMissingEpisodes": True}
        
        # Set all episodes to unmonitored by default in the add request
        for season in series_data.get("seasons", []):
            season["monitored"] = False

        add_url = f"{self.base_url}/api/v3/series"
        response = requests.post(add_url, json=series_data, headers=self.headers, timeout=15)
        response.raise_for_status()
        added_series = response.json()
        series_id = added_series["id"]

        # Now monitor the first X episodes
        self.monitor_episodes(series_id, tasting_count)
        
        return added_series

    def monitor_episodes(self, series_id, count):
        # Get episode list for the series
        ep_url = f"{self.base_url}/api/v3/episode"
        params = {"seriesId": series_id}
        ep_res = requests.get(ep_url, params=params, headers=self.headers)
        ep_res.raise_for_status()
        episodes = ep_res.json()

        # Sort episodes by season and number
        episodes.sort(key=lambda x: (x['seasonNumber'], x['episodeNumber']))
        
        # Filter out specials (Season 0)
        regular_episodes = [e for e in episodes if e['seasonNumber'] > 0]
        
        target_ids = [e['id'] for e in regular_episodes[:count]]
        
        monitor_url = f"{self.base_url}/api/v3/episode/monitor"
        payload = {
            "episodeIds": target_ids,
            "monitored": True
        }
        requests.put(monitor_url, json=payload, headers=self.headers).raise_for_status()

    def commit_series(self, series_id):
        # Monitor all episodes and the series itself
        url = f"{self.base_url}/api/v3/series/{series_id}"
        series_res = requests.get(url, headers=self.headers, timeout=10)
        series_res.raise_for_status()
        series_data = series_res.json()
        
        series_data["monitored"] = True
        for season in series_data["seasons"]:
            season["monitored"] = True
            
        requests.put(url, json=series_data, headers=self.headers).raise_for_status()
        
        # Also trigger a search for the now monitored episodes
        search_url = f"{self.base_url}/api/v3/command"
        search_payload = {"name": "SeriesSearch", "seriesId": series_id}
        requests.post(search_url, json=search_payload, headers=self.headers).raise_for_status()

    def delete_series(self, series_id):
        url = f"{self.base_url}/api/v3/series/{series_id}"
        # deleteFiles=true ensures it is removed from disk
        params = {"deleteFiles": "true"}
        requests.delete(url, params=params, headers=self.headers).raise_for_status()

    def get_series(self, series_id):
        url = f"{self.base_url}/api/v3/series/{series_id}"
        response = requests.get(url, headers=self.headers, timeout=10)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()
