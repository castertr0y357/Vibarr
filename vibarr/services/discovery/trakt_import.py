import csv
import io
import logging
from datetime import datetime
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from .trakt_service import TraktService
from ...models import MediaWatchEvent, MediaType, MediaServerType

logger = logging.getLogger(__name__)

def import_trakt_history_from_api(username: str) -> int:
    """
    Fetches the user's Trakt history from the public API
    and saves the records to the MediaWatchEvent table.
    """
    service = TraktService()
    history = service.get_user_history(username, limit=100)
    if not history:
        logger.info(f"Trakt Importer - Info - No history fetched for '{username}'")
        return 0

    count = 0
    for item in history:
        try:
            history_id = item.get("id")
            if not history_id:
                continue

            event_id = f"trakt_history_{history_id}"
            if MediaWatchEvent.objects.filter(event_id=event_id).exists():
                continue

            watched_at_str = item.get("watched_at")
            watched_at = parse_datetime(watched_at_str) if watched_at_str else timezone.now()

            media_type_str = item.get("type")
            if media_type_str == "movie":
                movie_data = item.get("movie", {})
                title = movie_data.get("title")
                tmdb_id = movie_data.get("ids", {}).get("tmdb")
                m_type = MediaType.MOVIE
                season, episode = 1, 1
            elif media_type_str == "episode":
                episode_data = item.get("episode", {})
                show_data = item.get("show", {})
                title = show_data.get("title")
                tmdb_id = show_data.get("ids", {}).get("tmdb")
                m_type = MediaType.SHOW
                season = episode_data.get("season", 1)
                episode = episode_data.get("number", 1)
            else:
                continue

            if not title:
                continue

            MediaWatchEvent.objects.create(
                event_id=event_id,
                source_server=MediaServerType.PLEX, # default backfill compatibility
                media_type=m_type,
                tmdb_id=tmdb_id,
                show_title=title,
                season=season,
                episode=episode,
                watched_at=watched_at
            )
            count += 1
        except Exception as e:
            logger.error(f"Trakt Importer - Error - Failed to parse API history item: {e}")
            continue

    logger.info(f"Trakt Importer - Info - Successfully imported {count} history items for '{username}'")
    return count

def import_trakt_watchlist_from_api(username: str) -> int:
    """
    Fetches the user's Trakt watchlist from the public API
    and seeds them as mock watch events to influence taste profiles.
    """
    service = TraktService()
    watchlist = service.get_user_watchlist(username)
    if not watchlist:
        logger.info(f"Trakt Importer - Info - No watchlist items fetched for '{username}'")
        return 0

    count = 0
    # Seed as recent watch events to anchor taste profiling
    now = timezone.now()
    for index, item in enumerate(watchlist):
        try:
            watchlist_id = item.get("id")
            if not watchlist_id:
                continue

            event_id = f"trakt_watchlist_{watchlist_id}"
            if MediaWatchEvent.objects.filter(event_id=event_id).exists():
                continue

            media_type_str = item.get("type")
            if media_type_str == "movie":
                movie_data = item.get("movie", {})
                title = movie_data.get("title")
                tmdb_id = movie_data.get("ids", {}).get("tmdb")
                m_type = MediaType.MOVIE
                season, episode = 1, 1
            elif media_type_str == "show":
                show_data = item.get("show", {})
                title = show_data.get("title")
                tmdb_id = show_data.get("ids", {}).get("tmdb")
                m_type = MediaType.SHOW
                season, episode = 1, 1
            else:
                continue

            if not title:
                continue

            # Spread them out slightly in time to look like history
            watched_at = now - timezone.timedelta(hours=index)

            MediaWatchEvent.objects.create(
                event_id=event_id,
                source_server=MediaServerType.PLEX,
                media_type=m_type,
                tmdb_id=tmdb_id,
                show_title=title,
                season=season,
                episode=episode,
                watched_at=watched_at
            )
            count += 1
        except Exception as e:
            logger.error(f"Trakt Importer - Error - Failed to parse API watchlist item: {e}")
            continue

    logger.info(f"Trakt Importer - Info - Successfully imported {count} watchlist items as seeds for '{username}'")
    return count

def import_trakt_csv(file_content: str) -> int:
    """
    Parses a CSV string exported from Trakt (or similar tools)
    and saves watch events to the MediaWatchEvent table.
    """
    csv_file = io.StringIO(file_content.strip())
    reader = csv.DictReader(csv_file)
    
    if not reader.fieldnames:
        logger.error("Trakt Importer - Error - CSV file is empty or headers missing")
        return 0

    # Flexible, case-insensitive header mapping
    headers = {f.lower().replace(" ", "_"): f for f in reader.fieldnames}
    
    tmdb_key = next((headers[k] for k in ["tmdb_id", "tmdb", "tmdbid", "id_tmdb"] if k in headers), None)
    title_key = next((headers[k] for k in ["title", "name", "show_title", "show_name"] if k in headers), None)
    type_key = next((headers[k] for k in ["type", "media_type", "mediatype"] if k in headers), None)
    watched_key = next((headers[k] for k in ["watched_at", "watched", "date", "time", "timestamp", "last_watched"] if k in headers), None)
    season_key = next((headers[k] for k in ["season", "season_number", "season_num"] if k in headers), None)
    episode_key = next((headers[k] for k in ["episode", "episode_number", "episode_num", "number"] if k in headers), None)

    if not title_key:
        logger.error("Trakt Importer - Error - Could not find a Title column in CSV")
        return 0

    count = 0
    now = timezone.now()
    for row_idx, row in enumerate(reader):
        try:
            title = row.get(title_key)
            if not title:
                continue

            # Read and resolve TMDB ID if present
            tmdb_val = row.get(tmdb_key) if tmdb_key else None
            tmdb_id = int(tmdb_val) if tmdb_val and tmdb_val.isdigit() else None

            # Read and normalize media type
            raw_type = (row.get(type_key) or "show").lower() if type_key else "show"
            m_type = MediaType.MOVIE if "movie" in raw_type else MediaType.SHOW

            # Unique event ID based on row index and title hash to prevent duplicate CSV imports
            event_hash = hash(f"{title}_{row_idx}")
            event_id = f"trakt_csv_{abs(event_hash)}"
            if MediaWatchEvent.objects.filter(event_id=event_id).exists():
                continue

            # Parse datetime
            watched_val = row.get(watched_key) if watched_key else None
            watched_at = timezone.now()
            if watched_val:
                try:
                    # Trakt datetime is typically ISO format: '2026-06-02T16:14:39.000Z'
                    watched_at = parse_datetime(watched_val) or datetime.strptime(watched_val, "%Y-%m-%d %H:%M:%S")
                    if timezone.is_naive(watched_at):
                        watched_at = timezone.make_aware(watched_at)
                except Exception:
                    pass # Fallback to now

            # Parse season and episode counts
            season_val = row.get(season_key) if season_key else None
            episode_val = row.get(episode_key) if episode_key else None
            season = int(season_val) if season_val and season_val.isdigit() else 1
            episode = int(episode_val) if episode_val and episode_val.isdigit() else 1

            MediaWatchEvent.objects.create(
                event_id=event_id,
                source_server=MediaServerType.PLEX,
                media_type=m_type,
                tmdb_id=tmdb_id,
                show_title=title,
                season=season,
                episode=episode,
                watched_at=watched_at
            )
            count += 1
        except Exception as e:
            logger.error(f"Trakt Importer - Error - Failed to parse CSV row {row_idx}: {e}")
            continue

    logger.info(f"Trakt Importer - Info - Successfully imported {count} rows from CSV")
    return count
