from plexapi.server import PlexServer
from django.conf import settings
from datetime import datetime, timedelta, timezone as dt_timezone
from django.utils import timezone
from .media_provider import MediaProvider
from ...models import AppConfig
import logging

logger = logging.getLogger(__name__)

class PlexService(MediaProvider):
    def __init__(self, url=None, token=None):
        config = AppConfig.get_solo()
        self.baseurl = url or config.plex_url or getattr(settings, 'PLEX_URL', '')
        self.token = token or config.plex_token or getattr(settings, 'PLEX_TOKEN', '')
        self._plex = None
        self._has_tested = False

    @property
    def plex(self):
        if self._plex is None and self.baseurl and self.token:
            try:
                from plexapi.server import PlexServer
                import requests
                
                # Setup session to allow insecure local connections if needed
                session = requests.Session()
                import re
                is_ip = re.match(r"https?://\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", self.baseurl)
                if is_ip:
                    session.verify = False
                    import urllib3
                    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                
                self._plex = PlexServer(self.baseurl, self.token, session=session)
            except Exception as e:
                logger.error(f"Plex Connection Error to {self.baseurl}: {e}")
                return None
        return self._plex

    def test_connection(self) -> bool:
        try:
            if not self.plex: return False
            self.plex.friendlyName
            return True
        except Exception:
            return False

    def get_recent_history(self, hours=24):
        if not self.plex: 
            logger.warning("Plex history requested but no connection established.")
            return []
        config = AppConfig.get_solo()
        monitored = [i.strip().lower() for i in config.monitored_libraries.split(',')] if config and config.monitored_libraries else []
        
        try:
            since_time = datetime.now(dt_timezone.utc) - timedelta(hours=hours)
            events = []
            
            # Use paginated history to avoid memory exhaustion on large libraries
            page_size = 100
            offset = 0
            
            while True:
                logger.info(f"Plex: Fetching history page (offset: {offset}, limit: {page_size})")
                
                params = {'sort': 'viewedAt:desc'}
                if config.plex_user_filter:
                    params['accountID'] = config.plex_user_filter
                
                headers = {
                    'X-Plex-Container-Start': str(offset),
                    'X-Plex-Container-Size': str(page_size)
                }
                
                history_xml = self.plex.query('/status/sessions/history/all', params=params, headers=headers)
                
                metadata_items = history_xml.findall('Metadata')
                if not metadata_items:
                    break
                
                for entry in metadata_items:
                    viewed_at = datetime.fromtimestamp(int(entry.attrib.get('viewedAt', 0)), tz=dt_timezone.utc)
                    if viewed_at < since_time:
                        return events # Done
                    
                    library_name = entry.attrib.get('librarySectionTitle')
                    if monitored and library_name and library_name.lower() not in monitored:
                        continue

                    m_type = entry.attrib.get('type')
                    if m_type in ['episode', 'movie']:
                        event = {
                            'history_id': entry.attrib.get('historyKey'),
                            'type': m_type,
                            'title': entry.attrib.get('grandparentTitle') if m_type == 'episode' else entry.attrib.get('title'),
                            'season': int(entry.attrib.get('parentIndex', 0)) if m_type == 'episode' else 0,
                            'episode': int(entry.attrib.get('index', 0)) if m_type == 'episode' else 0,
                            'watched_at': viewed_at,
                            'user_id': entry.attrib.get('accountID', 'admin'),
                            'rating': float(entry.attrib.get('userRating', 10.0)),
                            'view_offset': int(entry.attrib.get('viewOffset', 0)),
                            'duration': int(entry.attrib.get('duration', 0))
                        }
                        events.append(event)
                
                offset += page_size
                if len(events) > 5000: # Safety cap per provider

                    logger.warning("Plex: Reached safety cap of 5000 history items per poll.")
                    break
            
            if not events:
                # Fallback: Scan libraries for watched items
                logger.info("Plex history endpoint returned 0. Falling back to library scan...")
                for section in self.plex.library.sections():
                    library_name = section.title.lower()
                    if monitored and library_name not in monitored: continue
                    if section.type not in ['show', 'movie']: continue
                    
                    # Search for watched items
                    libtype = 'episode' if section.type == 'show' else None
                    watched_items = section.search(unwatched=False, libtype=libtype)
                    
                    # Determine limit based on backfill
                    limit = None if hours > 24 else 50
                    items_to_process = watched_items if limit is None else watched_items[:limit]
                    
                    logger.info(f"Scanning section {section.title}: Found {len(watched_items)} watched items. Processing {len(items_to_process)}.")
                    for item in items_to_process:
                        last_viewed = getattr(item, 'lastViewedAt', None)
                        if last_viewed and last_viewed.tzinfo is None:
                            last_viewed = timezone.make_aware(last_viewed)
                        
                        if not last_viewed:
                            last_viewed = timezone.now()
                            
                        event = {
                            'history_id': f"fallback_{item.ratingKey}",
                            'type': 'movie' if item.type == 'movie' else 'episode',
                            'title': item.grandparentTitle if item.type == 'episode' else item.title,
                            'season': int(item.parentIndex if item.type == 'episode' else 0),
                            'episode': int(item.index if item.type == 'episode' else 0),
                            'watched_at': last_viewed,
                            'user_id': 'admin',
                            'rating': float(item.userRating if item.userRating is not None else 10.0),
                            'view_offset': 0,
                            'duration': getattr(item, 'duration', 0)
                        }
                        events.append(event)
            
            return events
        except Exception as e:
            logger.error(f"Plex History Error: {e}")
            return []

    def get_available_libraries(self) -> list[str]:
        if not self.plex: return []
        try:
            return [section.title for section in self.plex.library.sections() if section.type in ['show', 'movie']]
        except Exception:
            return []

    def get_library_titles(self, force_refresh=False):
        if not self.plex: return []
        from django.core.cache import cache
        
        cache_key = 'plex_library_titles'
        if not force_refresh:
            cached_titles = cache.get(cache_key)
            if cached_titles: return cached_titles

        config = AppConfig.objects.first()
        monitored = [i.strip().lower() for i in config.monitored_libraries.split(',')] if config and config.monitored_libraries else []
        
        try:
            titles = []
            for section in self.plex.library.sections():
                if monitored and section.title.lower() not in monitored: continue
                if section.type in ['show', 'movie']:
                    # Optimization: only fetch title attribute
                    titles.extend([item.title for item in section.search()])
            
            unique_titles = list(set(titles))
            cache.set(cache_key, unique_titles, 3600)
            return unique_titles
        except Exception: return []

    def sync_collection(self, titles, collection_name):
        if not self.plex: return
        """Efficiently adds items to a collection."""
        import logging
        logger = logging.getLogger(__name__)
        
        # Batch by section to avoid redundant section loops
        sections = [s for s in self.plex.library.sections() if s.type in ['show', 'movie']]
        
        for section in sections:
            # Search for all titles in this section in one go if possible?
            # PlexAPI doesn't support bulk title search well, but we can search once per section
            # and then filter the results in memory.
            all_items = section.all()
            items_to_add = [item for item in all_items if item.title.lower() in [t.lower() for t in titles]]
            
            for item in items_to_add:
                try:
                    item.addCollection(collection_name)
                    logger.info(f"Plex: Added '{item.title}' to Collection '{collection_name}'")
                except Exception: continue
