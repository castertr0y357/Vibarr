from plexapi.server import PlexServer
from django.conf import settings
from datetime import datetime, timedelta, timezone
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
                self._plex = PlexServer(self.baseurl, self.token)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Plex Connection Error to {self.baseurl}: {e}")
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
            params = {'sort': 'viewedAt:desc'}
            if config.plex_user_filter:
                params['accountID'] = config.plex_user_filter

            history = self.plex.query('/status/sessions/history/all', params=params)
            since_time = datetime.now(timezone.utc) - timedelta(hours=hours)
            
            events = []
            for entry in history.findall('Metadata'):
                viewed_at = datetime.fromtimestamp(int(entry.attrib.get('viewedAt', 0)), tz=timezone.utc)
                if viewed_at < since_time:
                    break # Since we sorted by viewedAt:desc, we can stop early
                
                library_name = entry.attrib.get('librarySectionTitle')
                if library_name and library_name.lower() in ignored:
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
                        'user_id': entry.attrib.get('accountID'),
                        'rating': float(entry.attrib.get('userRating', 10.0)),
                        'view_offset': int(entry.attrib.get('viewOffset', 0)),
                        'duration': int(entry.attrib.get('duration', 0))
                    }
                    events.append(event)
            if not events:
                # Fallback: Scan libraries for watched items
                logger.info("Plex history endpoint returned 0. Falling back to library scan...")
                for section in self.plex.library.sections():
                    library_name = section.title.lower()
                    if monitored and library_name not in monitored: continue
                    if section.type not in ['show', 'movie']: continue
                    
                    # Search for watched items
                    watched_items = section.search(unwatched=False)
                    logger.info(f"Scanning section {section.title}: Found {len(watched_items)} watched items.")
                    for item in watched_items[:20]: # Limit to 20 per section to avoid flooding
                        event = {
                            'history_id': f"fallback_{item.ratingKey}",
                            'type': 'movie' if section.type == 'movie' else 'show',
                            'title': item.title,
                            'season': 0,
                            'episode': 0,
                            'watched_at': getattr(item, 'lastViewedAt', datetime.now(timezone.utc)),
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
