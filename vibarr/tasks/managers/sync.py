from ...models import Show, Recommendation, ShowState, MediaType, AppConfig
from ...services.discovery.ai_service import AIService
from ...services.discovery.tmdb_service import TMDBService
from ...services.managers.sonarr_service import SonarrService
from ...services.managers.radarr_service import RadarrService
from ...utils.providers import get_active_providers
from ...services.comms.notification_service import NotificationService
from django_q.tasks import async_task
import logging
import time

logger = logging.getLogger(__name__)

def discover_universe_and_sync(show_id, library_ids=None):
    try:
        show = Show.objects.get(id=show_id)
    except Show.DoesNotExist:
        return
        
    ai = AIService()
    tmdb = TMDBService()
    providers = get_active_providers()
    
    collection_name = None
    members = set()
    
    # 1. Try TMDB Collections (for movies) - 100% accuracy for franchises
    if show.media_type == MediaType.MOVIE:
        details = tmdb.get_movie_details(show.tmdb_id)
        if details and details.get('belongs_to_collection'):
            coll = tmdb.get_collection(details['belongs_to_collection']['id'])
            if coll:
                collection_name = coll['name']
                members.update([m.get('title') or m.get('name') for m in coll.get('parts', [])])
                logger.info(f"[Universe Architect] Found TMDB Collection: {collection_name} ({len(members)} parts)")
    
    # 2. AI Discovery (for broader Cinematic Universes and TV tie-ins)
    universe = ai.identify_universe(show.title)
    if universe.get('universe_name'):
        # Prefer the AI name if it identifies a broader universe (e.g. MCU vs Iron Man Collection)
        # or if we haven't found a collection yet.
        if not collection_name or len(universe['members']) > len(members):
            collection_name = universe['universe_name']
        members.update(universe['members'])
        
    if not collection_name:
        logger.info(f"[Universe Architect] No universe identified for '{show.title}'.")
        return
        
    logger.info(f"[Universe Architect] Architecting the '{collection_name}' universe for '{show.title}'.")
    
    # Tag current show with universe
    show.universe_name = collection_name
    show.save()
    
    config = AppConfig.get_solo()
    if config.auto_collection_sync:
        for _, provider in providers:
            provider.sync_collection(list(members), collection_name)
    
    if library_ids is None:
        library_ids = {}
        for _, provider in providers:
            library_ids.update(provider.get_library_identifiers())
        
        # Cross-check with Managers (Radarr/Sonarr)
        library_ids.update({str(id): "Radarr" for id in RadarrService().get_all_tmdb_ids()})
        library_ids.update({str(id): "Sonarr" for id in SonarrService().get_all_tvdb_ids()})
    
    # Ensure all keys are strings for robust lookup
    library_ids = {str(k): v for k, v in library_ids.items()}

    # gathered_candidates will hold the rich metadata and resolved IDs
    gathered_candidates = []
    
    for member_title in members:
        try:
            time.sleep(0.3) # Throttle to avoid TMDB rate limits
            
            search_res = tmdb.search_movie(member_title) or tmdb.search_show(member_title)
            if not search_res:
                logger.warning(f"[Universe Architect] Could not find TMDB record for universe member: {member_title}")
                continue
                
            tmdb_id = str(search_res['id'])
            m_type = MediaType.MOVIE if 'title' in search_res else MediaType.SHOW
            
            # Fetch rich metadata to get external IDs (TVDB/IMDB) for manager matching
            details = tmdb.get_movie_details(tmdb_id) if m_type == MediaType.MOVIE else tmdb.get_show_details(tmdb_id)
            if not details: continue

            tvdb_id = str(details.get('external_ids', {}).get('tvdb_id', ''))
            imdb_id = details.get('external_ids', {}).get('imdb_id')
            
            # Match against library (Plex/Jellyfin) OR Managers (Radarr/Sonarr)
            in_library = tmdb_id in library_ids or tvdb_id in library_ids or member_title.lower() in library_ids
            
            rating, advisory = tmdb.parse_advisory(details, is_movie=(m_type == MediaType.MOVIE))
            avg_runtime = details.get('episode_run_time', [0])[0] if details.get('episode_run_time') else details.get('runtime', 120)
            
            # Extract providers directly from appended data
            provider_results = details.get('watch/providers', {}).get('results', {}).get(tmdb.region, {})
            flatrate = provider_results.get('flatrate', [])
            providers_str = ", ".join([p['provider_name'] for p in flatrate])

            # Decide state
            existing_show = Show.objects.filter(tmdb_id=tmdb_id, media_type=m_type).first()
            state = existing_show.state if existing_show else (ShowState.COMMITTED if in_library else ShowState.SUGGESTED)
            if state == ShowState.SUGGESTED and in_library: state = ShowState.COMMITTED

            gathered_candidates.append({
                'tmdb_id': tmdb_id,
                'media_type': m_type,
                'title': search_res.get('title') or search_res.get('name'),
                'overview': search_res.get('overview', ''),
                'poster_path': search_res.get('poster_path'),
                'imdb_id': imdb_id,
                'tvdb_id': tvdb_id,
                'imdb_rating': search_res.get('vote_average'),
                'runtime': avg_runtime,
                'content_rating': rating,
                'content_advisory': advisory,
                'streaming_providers': providers_str,
                'state': state,
                'tasting_episodes_count': 1 if m_type == MediaType.MOVIE else 3
            })
        except Exception as e:
            logger.error(f"[Universe Architect] Error gathering metadata for '{member_title}': {e}")

    if not gathered_candidates:
        return

    # Batch Score with AI
    try:
        from ...utils.intelligence import get_weighted_history_profile
        # We'll use a mix of both types for a broad universe profile
        profile = get_weighted_history_profile(MediaType.MOVIE) + get_weighted_history_profile(MediaType.SHOW)
        profile = list(set(profile)) # Dedup
        
        # We might have a lot of items, so we batch the AI scoring (15 at a time)
        scored_results = []
        for i in range(0, len(gathered_candidates), 15):
            batch = gathered_candidates[i:i+15]
            scored_results.extend(ai.score_candidates(profile, batch))
            
        # Map scores back to gathered candidates
        scores_map = {s['title'].lower(): s for s in scored_results}
        
        for candidate in gathered_candidates:
            ai_data = scores_map.get(candidate['title'].lower(), {})
            ai_score = ai_data.get('score', candidate['imdb_rating'] or 5.0)
            ai_reasoning = ai_data.get('reasoning', f"Part of {collection_name}.")
            ai_tags = ", ".join(ai_data.get('vibe_tags', [])) if isinstance(ai_data.get('vibe_tags'), list) else ""

            # Save Show
            show_obj, _ = Show.objects.update_or_create(
                tmdb_id=candidate['tmdb_id'],
                media_type=candidate['media_type'],
                defaults={
                    'title': candidate['title'],
                    'universe_name': collection_name,
                    'poster_path': candidate['poster_path'],
                    'imdb_id': candidate['imdb_id'],
                    'tvdb_id': candidate['tvdb_id'],
                    'imdb_rating': candidate['imdb_rating'],
                    'runtime': candidate['runtime'],
                    'content_rating': candidate['content_rating'],
                    'content_advisory': candidate['content_advisory'],
                    'streaming_providers': candidate['streaming_providers'],
                    'state': candidate['state'],
                    'tasting_episodes_count': candidate['tasting_episodes_count']
                }
            )

            # Save Recommendation
            Recommendation.objects.update_or_create(
                suggested_show=show_obj,
                defaults={
                    'source_title': show.title, 
                    'score': ai_score, 
                    'reasoning': ai_reasoning, 
                    'vibe_tags': ai_tags
                }
            )
            
            # Check for Auto-Tasting if it's a new high-confidence match
            if candidate['state'] == ShowState.SUGGESTED and ai_score >= config.auto_tasting_threshold:
                current_tasting = Show.objects.filter(state=ShowState.TASTING).count()
                if current_tasting < config.max_tasting_items:
                    logger.info(f"[Universe Architect] High confidence universe match ({ai_score}) for '{show_obj.title}'. Auto-Tasting.")
                    async_task('vibarr.tasks.managers.actions.start_tasting', show_obj.id)

    except Exception as e:
        logger.error(f"[Universe Architect] AI Scoring failed: {e}. Falling back to default scores.")
        # Fallback loop (similar to old logic but simpler)
        for candidate in gathered_candidates:
            show_obj, _ = Show.objects.update_or_create(
                tmdb_id=candidate['tmdb_id'],
                media_type=candidate['media_type'],
                defaults={'title': candidate['title'], 'universe_name': collection_name, 'state': candidate['state']}
            )
            Recommendation.objects.get_or_create(
                suggested_show=show_obj,
                defaults={'source_title': show.title, 'score': 5.0, 'reasoning': f"Part of {collection_name}."}
            )
    
    logger.info(f"[Universe Architect] Completed sync for '{collection_name}': {len(members)} members processed.")
    NotificationService().notify_universe_found(show.title, collection_name, len(members))

def batch_universe_sync():
    """Batches universe discovery for all active/watched shows by dispatching individual tasks."""
    active_shows = Show.objects.filter(state__in=[ShowState.TASTING, ShowState.COMMITTED, ShowState.WATCHED])
    
    logger.info(f"[Universe Architect] Starting batch sync for {active_shows.count()} shows.")
    
    for show in active_shows:
        async_task(discover_universe_and_sync, show.id)

def sync_external_states():
    active_items = Show.objects.filter(state__in=[ShowState.TASTING, ShowState.COMMITTED])
    sonarr = SonarrService()
    radarr = RadarrService()
    
    for item in active_items:
        try:
            if item.media_type == MediaType.SHOW and item.sonarr_id:
                if not sonarr.get_series(item.sonarr_id):
                    item.state = ShowState.REJECTED
                    item.save()
            elif item.radarr_id:
                if not radarr.get_movie(item.radarr_id):
                    item.state = ShowState.REJECTED
                    item.save()
        except Exception as e:
            logger.error(f"[Universe Architect] Error syncing external state for {item.title}: {e}")
            continue
