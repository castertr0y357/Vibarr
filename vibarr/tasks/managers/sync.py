from ...models import Show, Recommendation, ShowState, MediaType, AppConfig
from ...services.discovery.ai_service import AIService
from ...services.discovery.tmdb_service import TMDBService
from ...services.managers.sonarr_service import SonarrService
from ...services.managers.radarr_service import RadarrService
from ...utils.providers import get_active_providers
from ...utils.tasting import calculate_tasting_count
from ...services.comms.notification_service import NotificationService
from django_q.tasks import async_task
import logging
import time
import re
from ...utils.intelligence import get_weighted_history_profile
from ...services.discovery.heuristic_ranking import HeuristicRankingService

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
                logger.info(f"Universe Architect - Info - Found TMDB Collection: {collection_name} ({len(members)} parts)")
    
    # 2. AI Discovery (for broader Cinematic Universes and TV tie-ins)
    universe = ai.identify_universe(show.title)
    if universe.get('universe_name'):
        # Prefer the AI name if it identifies a broader universe (e.g. MCU vs Iron Man Collection)
        # or if we haven't found a collection yet.
        if not collection_name or len(universe['members']) > len(members):
            collection_name = universe['universe_name']
        members.update(universe['members'])
        
    if not collection_name:
        logger.info(f"Universe Architect - Info - No universe identified for '{show.title}'.")
        return
        
    logger.info(f"Universe Architect - Info - Architecting the '{collection_name}' universe for '{show.title}'.")
    
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
                logger.warning(f"Universe Architect - Warning - Could not find TMDB record for universe member: {member_title}")
                continue
                
            # Prevent false positives (titles that sound similar/vague, or random TMDB fuzzy matches)
            clean_member = re.sub(r'\((?:19|20)\d{2}\)', '', member_title).strip().lower()
            resolved_title = search_res.get('title') or search_res.get('name') or ''
            clean_resolved = resolved_title.lower()
            
            member_words = set(re.findall(r'\w+', clean_member))
            resolved_words = set(re.findall(r'\w+', clean_resolved))
            
            # They must share at least one significant alphanumeric word (longer than 2 chars)
            # or be sub-strings of each other
            sig_member_words = {w for w in member_words if len(w) > 2}
            sig_resolved_words = {w for w in resolved_words if len(w) > 2}
            
            # Edge case: short titles
            if not sig_member_words:
                sig_member_words = member_words
            if not sig_resolved_words:
                sig_resolved_words = resolved_words
                
            has_overlap = bool(sig_member_words & sig_resolved_words)
            is_substring = clean_member in clean_resolved or clean_resolved in clean_member
            
            if not (has_overlap or is_substring):
                logger.warning(f"Universe Architect - Warning - Title match verification failed for member '{member_title}'. Got search result '{resolved_title}'. Skipping.")
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
            
            provider_results = details.get('watch/providers', {}).get('results', {}).get(tmdb.region, {})
            flatrate = provider_results.get('flatrate', [])
            providers_str = ", ".join([p['provider_name'] for p in flatrate])

            # Season 1 logic
            season_one_episodes = 0
            if m_type == MediaType.SHOW and details.get('seasons'):
                s1 = next((s for s in details['seasons'] if s.get('season_number') == 1), None)
                if s1:
                    season_one_episodes = s1.get('episode_count', 0)

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
                'first_season_episodes': season_one_episodes if m_type == MediaType.SHOW else None,
                'tasting_episodes_count': 1 if m_type == MediaType.MOVIE else calculate_tasting_count(avg_runtime, season_one_episodes)
            })
        except Exception as e:
            logger.error(f"Universe Architect - Error - Error gathering metadata for '{member_title}': {e}")

    if not gathered_candidates:
        return

    # Batch Score with AI or Heuristics
    try:
        # We'll use a mix of both types for a broad universe profile
        raw_profile = get_weighted_history_profile(MediaType.MOVIE) + get_weighted_history_profile(MediaType.SHOW)
        seen = set()
        profile = []
        for p in raw_profile:
            title = p['title'] if isinstance(p, dict) else p
            if title not in seen:
                seen.add(title)
                profile.append(p)
        
        scores_map = {}
        if config.use_ai_recommendations:
            # We might have a lot of items, so we batch the AI scoring (15 at a time)
            scored_results = []
            for i in range(0, len(gathered_candidates), 15):
                batch = gathered_candidates[i:i+15]
                scored_results.extend(ai.score_candidates(profile, batch))
                
            # Map scores back to gathered candidates
            scores_map = {s['title'].lower(): s for s in scored_results}
        else:
            hrs = HeuristicRankingService(config)
            user_profile_movie = hrs._build_user_profile(MediaType.MOVIE)
            user_profile_show = hrs._build_user_profile(MediaType.SHOW)
            seerr_profile = hrs._build_seerr_profile() if config.use_seerr else set()
            seerr_tag_profile = hrs._build_seerr_tag_profile() if config.use_seerr else {}
            
            for candidate in gathered_candidates:
                m_type = candidate['media_type']
                user_profile = user_profile_movie if m_type == MediaType.MOVIE else user_profile_show
                # Adapt candidate to format hrs._calculate_score expects
                cand_adapted = {
                    'id': int(candidate['tmdb_id']),
                    'title': candidate['title'],
                    'vote_average': candidate['imdb_rating'] or 0.0,
                    'popularity': 0.0,
                    'genre_ids': [], # Details will load genres in HeuristicRankingService anyway
                }
                res = hrs._calculate_score(cand_adapted, m_type, user_profile, seerr_profile, seerr_tag_profile)
                scores_map[candidate['title'].lower()] = {
                    'score': res['score'],
                    'reasoning': res['reasoning'],
                    'vibe_tags': res['vibe_tags']
                }
        
        for candidate in gathered_candidates:
            score_data = scores_map.get(candidate['title'].lower(), {})
            score = score_data.get('score', candidate['imdb_rating'] or 5.0)
            reasoning = score_data.get('reasoning', f"Part of {collection_name}.")
            tags = ", ".join(score_data.get('vibe_tags', [])) if isinstance(score_data.get('vibe_tags'), list) else ""

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
                    'first_season_episodes': candidate.get('first_season_episodes'),
                    'tasting_episodes_count': candidate['tasting_episodes_count']
                }
            )

            # Save Recommendation
            Recommendation.objects.update_or_create(
                suggested_show=show_obj,
                defaults={
                    'source_title': show.title, 
                    'score': score, 
                    'reasoning': reasoning, 
                    'vibe_tags': tags
                }
            )
            
            # Check for Auto-Tasting if it's a new high-confidence match
            if config.enable_auto_tasting and candidate['state'] == ShowState.SUGGESTED and score >= config.auto_tasting_threshold:
                current_tasting = Show.objects.filter(state=ShowState.TASTING).count()
                if current_tasting < config.max_tasting_items:
                    logger.info(f"Universe Architect - Info - High confidence universe match ({score}) for '{show_obj.title}'. Auto-Tasting.")
                    async_task('vibarr.tasks.managers.actions.start_tasting', show_obj.id)

    except Exception as e:
        logger.error(f"Universe Architect - Error - AI Scoring failed: {e}. Falling back to default scores.")
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
    
    logger.info(f"Universe Architect - Info - Completed sync for '{collection_name}': {len(members)} members processed.")
    NotificationService().notify_universe_found(show.title, collection_name, len(members))

    # Enforce backlog limits
    from ..discovery.recommendations import prune_discovery_backlog
    prune_discovery_backlog(MediaType.MOVIE)
    prune_discovery_backlog(MediaType.SHOW)

def batch_universe_sync():
    """Batches universe discovery for all active/watched shows by dispatching individual tasks."""
    active_shows = Show.objects.filter(state__in=[ShowState.TASTING, ShowState.COMMITTED, ShowState.WATCHED])
    
    logger.info(f"Universe Architect - Info - Starting batch sync for {active_shows.count()} shows.")
    
    for show in active_shows:
        async_task(discover_universe_and_sync, show.id)

def sync_external_states():
    """
    Periodic maintenance task to ensure Vibarr's state matches Sonarr/Radarr.
    Fixes monitoring issues and handles cases where items were deleted externally.
    """
    active_items = Show.objects.filter(state__in=[ShowState.TASTING, ShowState.COMMITTED])
    sonarr = SonarrService()
    radarr = RadarrService()
    
    for item in active_items:
        try:
            if item.media_type == MediaType.SHOW and item.sonarr_id:
                s_details = sonarr.get_series(item.sonarr_id)
                if not s_details:
                    logger.warning(f"State Sync - Warning - Show '{item.title}' (ID: {item.sonarr_id}) not found in Sonarr. Marking as REJECTED.")
                    item.state = ShowState.REJECTED
                    item.save()
                    continue

                # 1. Health Check: Monitoring Status
                is_monitored = s_details.get('monitored', False)
                
                if item.state == ShowState.COMMITTED:
                    # For committed shows, series AND all seasons should be monitored
                    has_unmonitored_season = any(not s.get('monitored') for s in s_details.get('seasons', []))
                    if not is_monitored or has_unmonitored_season:
                        logger.info(f"State Sync - Info - Healing monitoring for committed show: {item.title} (Series: {is_monitored}, Seasons: {not has_unmonitored_season})")
                        sonarr.commit_series(item.sonarr_id)
                
                elif item.state == ShowState.TASTING:
                    # For tasting, series must be monitored
                    if not is_monitored:
                        logger.info(f"State Sync - Info - Healing series-level monitoring for tasting show: {item.title}")
                        s_details['monitored'] = True
                        sonarr.update_series(s_details)
                        # Re-run granular monitoring to be safe
                        sonarr.monitor_episodes(item.sonarr_id, item.tasting_episodes_count)
                    else:
                        # Even if series is monitored, ensure Season 1 and some episodes are
                        has_monitored_season = any(s.get('monitored') and s.get('seasonNumber') == 1 for s in s_details.get('seasons', []))
                        if not has_monitored_season:
                            logger.info(f"State Sync - Info - Healing season-level monitoring for tasting show: {item.title}")
                            sonarr.monitor_episodes(item.sonarr_id, item.tasting_episodes_count)

                # 2. Check if it's actually downloading
                queue = sonarr.get_series_queue(item.sonarr_id)
                if not queue and item.state == ShowState.TASTING:
                    logger.debug(f"State Sync - Debug - Tasting '{item.title}' is monitored in Sonarr but nothing in queue.")

            elif item.media_type == MediaType.MOVIE and item.radarr_id:
                m_details = radarr.get_movie(item.radarr_id)
                if not m_details:
                    logger.warning(f"State Sync - Warning - Movie '{item.title}' (ID: {item.radarr_id}) not found in Radarr. Marking as REJECTED.")
                    item.state = ShowState.REJECTED
                    item.save()
                    continue
                
                # Ensure it is monitored
                if not m_details.get('monitored'):
                    logger.info(f"State Sync - Info - Healing monitoring for movie in Radarr: {item.title}")
                    m_details['monitored'] = True
                    radarr.update_movie(m_details)

                # Queue check for Radarr
                # (I haven't implemented get_movie_queue yet, so we'll just check full queue if needed)
                # For now, Radarr is usually more straightforward.

        except Exception as e:
            logger.error(f"State Sync - Error - Error maintaining state for {item.title}: {e}")
            continue
