import requests
from typing import List, Dict, Any
import logging
from .media_provider import MediaProvider
from ...models import AppConfig
from datetime import datetime, timedelta, timezone
from django.core.cache import cache
from django.utils import timezone as django_timezone

logger = logging.getLogger(__name__)

class JellyfinService(MediaProvider):
    def __init__(self, url=None, api_key=None):
        config = AppConfig.objects.first()
        self.base_url = url or (config.jellyfin_url if config else None)
        self.api_key = api_key or (config.jellyfin_api_key if config else None)
        self.headers = {
            "X-Emby-Token": self.api_key,
            "Content-Type": "application/json"
        }

    def test_connection(self) -> bool:
        if not self.base_url or not self.api_key:
            return False
        try:
            url = f"{self.base_url}/System/Info"
            response = requests.get(url, headers=self.headers, timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Jellyfin: Connection test failed: {e}")
            return False

    def get_library_titles(self) -> List[str]:
        if not self.base_url: return []
        cache_key = 'jellyfin_library_titles'
        cached = cache.get(cache_key)
        if cached: return cached

        config = AppConfig.objects.first()
        monitored = set(i.strip().lower() for i in config.monitored_libraries.split(',')) if config and config.monitored_libraries else set()

        try:
            # Get available folders first to filter by name
            folders_url = f"{self.base_url}/Library/VirtualFolders"
            folders_res = requests.get(folders_url, headers=self.headers, timeout=5)
            if folders_res.status_code != 200: return []
            
            allowed_ids = [f['ItemId'] for f in folders_res.json() if not monitored or f['Name'].lower() in monitored]
            if not allowed_ids: return []

            # Get all Movies and Series within allowed folders
            url = f"{self.base_url}/Items"
            params = {
                "IncludeItemTypes": "Movie,Series",
                "Recursive": True,
                "Fields": "Name",
                "IsMissing": False,
                "ParentId": ",".join(allowed_ids)
            }
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                titles = [item['Name'] for item in data.get('Items', [])]
                cache.set(cache_key, titles, 900) # 15 minutes
                return titles
            return []
        except Exception as e:
            logger.error(f"Jellyfin: Failed to fetch library titles: {e}")
            return []

    def get_library_identifiers(self, force_refresh=False):
        if not self.base_url: return {}
        cache_key = 'jellyfin_library_identifiers'
        if not force_refresh:
            cached = cache.get(cache_key)
            if cached: return cached

        config = AppConfig.objects.first()
        monitored = set(i.strip().lower() for i in config.monitored_libraries.split(',')) if config and config.monitored_libraries else set()

        try:
            folders_url = f"{self.base_url}/Library/VirtualFolders"
            folders_res = requests.get(folders_url, headers=self.headers, timeout=5)
            if folders_res.status_code != 200: return {}
            
            allowed_ids = [f['ItemId'] for f in folders_res.json() if not monitored or f['Name'].lower() in monitored]
            if not allowed_ids: return {}

            url = f"{self.base_url}/Items"
            params = {
                "IncludeItemTypes": "Movie,Series",
                "Recursive": True,
                "Fields": "Name,ProviderIds",
                "IsMissing": False,
                "ParentId": ",".join(allowed_ids)
            }
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            identifiers = {}
            if response.status_code == 200:
                data = response.json()
                for item in data.get('Items', []):
                    tmdb_id = item.get('ProviderIds', {}).get('Tmdb')
                    if tmdb_id:
                        identifiers[str(tmdb_id)] = item['Name']
                    else:
                        identifiers[item['Name'].lower()] = item['Name']
                
                cache.set(cache_key, identifiers, 900)
            return identifiers
        except Exception as e:
            logger.error(f"Jellyfin: Failed to fetch library identifiers: {e}")
            return {}

    def get_recent_history(self, hours: int = 1) -> List[Dict[str, Any]]:
        """Jellyfin doesn't have a direct 'global history' endpoint as easily as Plex.
        We typically poll for 'UserActivity' or use a plugin like Jellystat.
        For this implementation, we'll check the 'Items' with a modified date or 'PlaybackInfo' if possible.
        A better way is to check 'ActivityLog' for playback events.
        """
        if not self.base_url: return []
        try:
            url = f"{self.base_url}/System/ActivityLog/Entries"
            params = {
                "MinDate": (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat(),
            }
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            if response.status_code != 200: return []
            
            # This logic is complex because Jellyfin log is verbose.
            # Usually, we'd want to use a webhook or Jellystat.
            # For now, let's just return an empty list or implement basic parsing.
            return [] 
        except Exception:
            return []

    def sync_collection(self, titles: List[str], collection_name: str):
        """Creates or updates a BoxSet in Jellyfin."""
        if not self.base_url: return
        try:
            # 1. Search for items to get their IDs
            item_ids = []
            for title in titles:
                search_url = f"{self.base_url}/Items"
                params = {
                    "SearchTerm": title,
                    "IncludeItemTypes": "Movie,Series",
                    "Recursive": True,
                    "Fields": "Name",
                    "Limit": 1
                }
                res = requests.get(search_url, headers=self.headers, params=params, timeout=5)
                if res.status_code == 200:
                    results = res.json().get('Items', [])
                    if results:
                        item_ids.append(results[0]['Id'])

            if not item_ids: return

            # 2. Check if collection already exists
            coll_url = f"{self.base_url}/Items"
            params = {"IncludeItemTypes": "BoxSet", "Recursive": True, "SearchTerm": collection_name}
            coll_res = requests.get(coll_url, headers=self.headers, params=params, timeout=5)
            
            collection_id = None
            if coll_res.status_code == 200:
                colls = coll_res.json().get('Items', [])
                for c in colls:
                    if c['Name'].lower() == collection_name.lower():
                        collection_id = c['Id']
                        break

            # 3. Create or Update
            if not collection_id:
                create_url = f"{self.base_url}/Collections"
                params = {"Name": collection_name, "Ids": ",".join(item_ids)}
                requests.post(create_url, headers=self.headers, params=params, timeout=10)
            else:
                update_url = f"{self.base_url}/Collections/{collection_id}/Items"
                params = {"Ids": ",".join(item_ids)}
                requests.post(update_url, headers=self.headers, params=params, timeout=10)
                
        except Exception as e:
            logger.error(f"Jellyfin: Collection Sync Error for '{collection_name}': {e}")

    def get_available_libraries(self) -> List[str]:
        if not self.base_url: return []
        try:
            url = f"{self.base_url}/Library/VirtualFolders"
            response = requests.get(url, headers=self.headers, timeout=5)
            if response.status_code == 200:
                return [folder['Name'] for folder in response.json()]
            return []
        except Exception as e:
            logger.error(f"Jellyfin: Failed to fetch libraries: {e}")
            return []
