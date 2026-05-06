from ...models import AppConfig, MediaWatchEvent, MediaServerType
from ...services.media.plex_service import PlexService
from ...services.media.jellyfin_service import JellyfinService
from ..discovery.recommendations import generate_recommendations
from ..managers.actions import check_tasting_progress, trigger_auto_purge
import logging

logger = logging.getLogger(__name__)

def get_active_providers():
    config = AppConfig.get_solo()
    providers = []
    if config.media_server_type in [MediaServerType.PLEX, MediaServerType.BOTH]:
        providers.append(('PLEX', PlexService()))
    if config.media_server_type in [MediaServerType.JELLYFIN, MediaServerType.BOTH]:
        providers.append(('JELLYFIN', JellyfinService()))
    return providers

def poll_media_servers(hours=1):
    config = AppConfig.get_solo()
    config.is_syncing = True
    config.sync_status = "Starting library synchronization..."
    config.save()

    try:
        providers = get_active_providers()
        for server_type, provider in providers:
            config.sync_status = f"Connecting to {server_type}..."
            config.save()
            poll_provider_history(server_type, hours=hours)
        
        from django.utils import timezone
        config.last_sync = timezone.now()
        config.is_syncing = False
        config.sync_status = "Sync complete."
        config.save()
    except Exception as e:
        logger.error(f"Sync error: {e}")
        config.is_syncing = False
        config.sync_status = f"Sync failed: {str(e)}"
        config.save()
    
    # Check for newly arrived tastings
    from ...models import Show, ShowState
    from ...services.comms.notification_service import NotificationService
    
    library_titles = []
    for _, provider in providers:
        library_titles.extend([t.lower() for t in provider.get_library_titles()])
    
    pending_tastings = Show.objects.filter(state=ShowState.TASTING, has_notified_ready=False)
    notifier = NotificationService()
    
    for show in pending_tastings:
        if show.title.lower() in library_titles:
            notifier.notify_tasting_ready(show.title)
            show.has_notified_ready = True
            show.save()

def resolve_tmdb_id(title, is_movie=False):
    from ...services.discovery.tmdb_service import TMDBService
    tmdb = TMDBService()
    result = tmdb.search_movie(title) if is_movie else tmdb.search_show(title)
    return result['id'] if result else None

def poll_provider_history(server_type, hours=1):
    from ...services.media.plex_service import PlexService
    from ...services.media.jellyfin_service import JellyfinService
    from ...models import AppConfig, MediaWatchEvent, MediaType
    
    config = AppConfig.get_solo()
    provider = PlexService() if server_type == 'PLEX' else JellyfinService()
    
    config.sync_status = f"Polling {server_type} for watch events (last {hours}h)..."
    config.save()
    
    logger.info(f"Polling {server_type} for new watch events (last {hours}h)...")
    try:
        events = provider.get_recent_history(hours=hours)
        logger.info(f"[{server_type}] Found {len(events)} events in last {hours}h.")
    except Exception as e:
        logger.error(f"[{server_type}] Failed to get history: {e}")
        return
    
    if not events:
        return

    # Optimization: Pre-fetch library titles once for this poll
    library_titles = [t.lower() for t in provider.get_library_titles()]
        
    for event in events:
        is_movie = event['type'] == 'movie'
        tmdb_id = resolve_tmdb_id(event['title'], is_movie=is_movie)
        
        obj, created = MediaWatchEvent.objects.get_or_create(
            event_id=f"{server_type}_{event['history_id']}",
            defaults={
                'source_server': server_type,
                'show_title': event['title'],
                'tmdb_id': tmdb_id,
                'media_type': MediaType.MOVIE if is_movie else MediaType.SHOW,
                'season': event['season'],
                'episode': event['episode'],
                'watched_at': event['watched_at'],
                'view_offset': event.get('view_offset'),
                'duration': event.get('duration'),
            }
        )
        
        # Always attempt recommendation generation - generate_recommendations has its own internal debounce
        from ..discovery.recommendations import generate_recommendations
        try:
            generate_recommendations(event['title'], is_movie=is_movie, library_titles=library_titles)
        except Exception as e:
            logger.error(f"Failed to generate recommendations for {event['title']}: {e}")
        
        if created:
            # Update event dict for consistency in progress check
            event['tmdb_id'] = tmdb_id
            check_tasting_progress(event)
            
        if event.get('rating') and event['rating'] <= 2.0:
            trigger_auto_purge(event['title'], tmdb_id=tmdb_id)
