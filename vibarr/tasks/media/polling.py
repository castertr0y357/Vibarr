import logging
import time
from datetime import timedelta

from django.utils import timezone
from django_q.tasks import async_task

from ...models import AppConfig, MediaWatchEvent, MediaServerType, Show, MediaType, ShowState
from ...services.media.plex_service import PlexService
from ...services.media.jellyfin_service import JellyfinService
from ...services.discovery.tmdb_service import TMDBService
from ...services.comms.notification_service import NotificationService
from ...utils.providers import get_active_providers
from ..discovery.recommendations import generate_recommendations
from ..managers.actions import check_tasting_progress, trigger_auto_purge

logger = logging.getLogger(__name__)

def poll_media_servers(hours=1):
    config = AppConfig.get_solo()
    now = timezone.now()
    
    # Robust lock: Allow if not syncing, OR if backfill (>24h), OR if stuck > 1 min
    stuck_threshold = 60 if hours > 24 else 900
    if config.is_syncing and config.last_sync and (now - config.last_sync).total_seconds() < stuck_threshold:
        logger.info(f"[Library Sync] Scout sync already in progress ({int((now - config.last_sync).total_seconds())}s ago). Skipping.")
        return

    config.is_syncing = True
    config.sync_status = "Starting library synchronization..."
    config.last_sync = now
    config.save()

    try:
        providers = get_active_providers()
        for server_type, provider in providers:
            config.sync_status = f"Connecting to {server_type}..."
            config.save()
            poll_provider_history(server_type, hours=hours)
        
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
    tmdb = TMDBService()
    result = tmdb.search_movie(title) if is_movie else tmdb.search_show(title)
    return result['id'] if result else None

def poll_provider_history(server_type, hours=1):
    config = AppConfig.get_solo()
    provider = PlexService() if server_type == 'PLEX' else JellyfinService()
    
    config.sync_status = f"Polling {server_type} for watch events (last {hours}h)..."
    config.save()
    
    logger.info(f"[Library Sync] Polling {server_type} for new watch events (last {hours}h)...")
    try:
        events = provider.get_recent_history(hours=hours)
        logger.info(f"[Library Sync] Found {len(events)} events for {server_type} in last {hours}h.")
    except Exception as e:
        logger.error(f"[Library Sync] Failed to get history for {server_type}: {e}")
        return
    
    if not events:
        return

    # Optimization: Pre-fetch library titles and existing Show mappings once
    library_titles = set(t.lower() for t in provider.get_library_titles())
    show_id_map = {s.title.lower(): s.tmdb_id for s in Show.objects.exclude(tmdb_id__isnull=True)}
    
    # Pre-fetch existing event_ids to eliminate N+1 existence checks
    incoming_event_ids = [f"{server_type}_{e['history_id']}" for e in events]
    existing_event_ids = set(MediaWatchEvent.objects.filter(event_id__in=incoming_event_ids).values_list('event_id', flat=True))

    # In-memory cache for TMDB IDs to avoid redundant API calls
    tmdb_cache = show_id_map.copy()
    total_events = len(events)
    processed = 0
    skipped = 0
    new_events = []
    
    recent_threshold = timezone.now() - timedelta(hours=24)
    recent_movie_events = {} # tmdb_id -> event
    recent_show_ids = set() # tmdb_id
    shows_to_purge = set() # (tmdb_id, title)
    
    for event in events:
        processed += 1
        event_id = f"{server_type}_{event['history_id']}"
        
        # Ensure watched_at is timezone-aware
        watched_at = event['watched_at']
        if watched_at and timezone.is_naive(watched_at):
            watched_at = timezone.make_aware(watched_at)
        
        try:
            # 1. Skip if already exists (Using pre-fetched set)
            if event_id in existing_event_ids:
                skipped += 1
                continue
                
            is_movie = event['type'] == 'movie'
            title = event['title']
            
            # 2. Check local cache for TMDB ID
            cache_key = title.lower()
            if cache_key in tmdb_cache:
                tmdb_id = tmdb_cache[cache_key]
            else:
                time.sleep(0.3) # Throttle history resolutions to prevent TMDB 429s
                tmdb_id = resolve_tmdb_id(title, is_movie=is_movie)
                tmdb_cache[cache_key] = tmdb_id
                
            # 3. Update status for UI feedback
            if processed % 10 == 0:
                percent = int((processed / max(1, total_events)) * 100)
                config.sync_status = f"Processing {server_type} history: {processed}/{total_events} ({percent}%)"
                config.save()

            new_event = MediaWatchEvent(
                event_id=event_id,
                source_server=server_type,
                show_title=title,
                tmdb_id=tmdb_id,
                media_type=MediaType.MOVIE if is_movie else MediaType.SHOW,
                season=event['season'],
                episode=event['episode'],
                watched_at=watched_at,
                view_offset=event.get('view_offset'),
                duration=event.get('duration'),
            )
            new_events.append(new_event)
            
            # 4. Collect "Active" logic targets for recent events
            is_recent = watched_at > recent_threshold
            if is_recent:
                event['tmdb_id'] = tmdb_id
                if is_movie:
                    # Keep the latest movie event for progress calculation
                    if tmdb_id not in recent_movie_events or watched_at > recent_movie_events[tmdb_id]['watched_at']:
                        recent_movie_events[tmdb_id] = event
                else:
                    recent_show_ids.add(tmdb_id)
                
                if event.get('rating') and event['rating'] <= 2.0:
                    shows_to_purge.add((tmdb_id, title))
                    
        except Exception as e:
            logger.error(f"Error processing history item '{event.get('title')}': {e}")
            continue

    # 5. Bulk Create all new events in one transaction
    if new_events:
        logger.info(f"[Library Sync] Bulk inserting {len(new_events)} new history events for {server_type} (Skipped {skipped} existing).")
        MediaWatchEvent.objects.bulk_create(new_events, ignore_conflicts=True)
    else:
        logger.info(f"[Library Sync] No new events to add for {server_type}. (Processed {total_events}, Skipped {skipped} existing).")

    # 6. Process "Active" logic outside the loop to minimize redundant queries
    for tmdb_id, event in recent_movie_events.items():
        check_tasting_progress(event)
    for tmdb_id in recent_show_ids:
        check_tasting_progress({'tmdb_id': tmdb_id})
    for tmdb_id, title in shows_to_purge:
        trigger_auto_purge(title, tmdb_id=tmdb_id)

    # After processing all history events, trigger recommendation generation 
    # for the most recent unique titles found in this poll.
    unique_shows = {} # title -> is_movie
    for event in events:
        unique_shows[event['title']] = (event['type'] == 'movie')
    
    # We limit to the top 5 most recent unique shows
    # Optimization: Only trigger recommendations if NOT in a deep backfill (> 24 hours)
    # to ensure the AI has the most complete taste profile first.
    if hours <= 24:
        for title, is_movie in list(unique_shows.items())[:5]:
            # Removed library_titles from payload to prevent Redis bloat
            async_task(generate_recommendations, title, is_movie=is_movie)
    else:
        logger.info(f"[{server_type}] Deep backfill detected ({hours}h). Skipping immediate recommendations.")

