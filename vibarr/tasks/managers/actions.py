from ...models import Show, ShowState, MediaType, MediaWatchEvent
from ...services.managers.sonarr_service import SonarrService
from ...services.managers.radarr_service import RadarrService
import logging

logger = logging.getLogger(__name__)

def start_tasting(show_id):
    show = Show.objects.get(id=show_id)
    try:
        if show.media_type == MediaType.MOVIE:
            radarr = RadarrService()
            added = radarr.add_movie(show.tmdb_id, show.title)
            show.radarr_id = added['id']
        else:
            sonarr = SonarrService()
            added = sonarr.add_series(show.tmdb_id, show.title, show.tasting_episodes_count)
            show.sonarr_id = added['id']
        show.state = ShowState.TASTING
        show.save()
    except Exception as e:
        logger.error(f"Error starting tasting for {show.title}: {e}")

def check_tasting_progress(event):
    tmdb_id = event.get('tmdb_id')
    if tmdb_id:
        show = Show.objects.filter(tmdb_id=tmdb_id, state=ShowState.TASTING).first()
    else:
        show = Show.objects.filter(title__icontains=event['title'], state=ShowState.TASTING).first()
        
    if not show: return

    if show.media_type == MediaType.MOVIE:
        if event.get('duration') and event.get('view_offset'):
            progress = (event['view_offset'] / event['duration']) * 100
            if progress >= 40:
                show.state = ShowState.COMMITTED
                show.save()
                from ...models import AppConfig
                config = AppConfig.get_solo()
                if config.auto_universe_discovery:
                    from .sync import discover_universe_and_sync
                    discover_universe_and_sync(show.id)
                from ..discovery.scouts import run_bridge_check
                run_bridge_check(show.id)
    else:
        # Use TMDB ID for counting if available
        if tmdb_id:
            watched_count = MediaWatchEvent.objects.filter(tmdb_id=tmdb_id).values('season', 'episode').distinct().count()
        else:
            watched_count = MediaWatchEvent.objects.filter(show_title__icontains=show.title).values('season', 'episode').distinct().count()
            
        threshold = max(2, show.tasting_episodes_count // 2)
        if watched_count >= threshold:
            sonarr = SonarrService()
            try:
                sonarr.commit_series(show.sonarr_id)
                show.state = ShowState.COMMITTED
                show.save()
                from ...models import AppConfig
                config = AppConfig.get_solo()
                if config.auto_universe_discovery:
                    from .sync import discover_universe_and_sync
                    discover_universe_and_sync(show.id)
                from ..discovery.scouts import run_bridge_check
                run_bridge_check(show.id)
                from ...services.comms.notification_service import NotificationService
                NotificationService().send_message(f"🏆 Tasting Complete! You've committed to the full series: <b>{show.title}</b>.", title="Series Committed")
            except Exception: pass

def trigger_auto_purge(title, tmdb_id=None):
    if tmdb_id:
        show = Show.objects.filter(tmdb_id=tmdb_id, state=ShowState.TASTING).first()
    else:
        show = Show.objects.filter(title__icontains=title, state=ShowState.TASTING).first()
        
    if show and (show.sonarr_id or show.radarr_id):
        logger.info(f"Auto-Purging {show.title} due to low rating.")
        if show.media_type == MediaType.MOVIE:
            radarr = RadarrService()
            try:
                radarr.delete_movie(show.radarr_id)
                show.state = ShowState.REJECTED
                show.save()
            except Exception: pass
        else:
            sonarr = SonarrService()
            try:
                sonarr.delete_series(show.sonarr_id)
                show.state = ShowState.REJECTED
                show.save()
            except Exception: pass
            
        from ...services.comms.notification_service import NotificationService
        NotificationService().notify_purge(show.title, "Low user rating / Negative vibe.")
