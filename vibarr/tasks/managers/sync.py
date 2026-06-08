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
    from ...models.universe import Universe
    universe_obj, _ = Universe.objects.get_or_create(name=collection_name)
    show.universes.add(universe_obj)
    show.universe_name = collection_name
    show.save()
    
    config = AppConfig.get_solo()
    if config.auto_collection_sync:
        for _, provider in providers:
            provider.sync_collection(list(members), collection_name)
    
    media_server_ids = {}
    radarr_ids_map = {}
    sonarr_ids_map = {}
    if library_ids is None:
        for _, provider in providers:
            media_server_ids.update(provider.get_library_identifiers())
        
        # Cross-check with Managers (Radarr/Sonarr)
        radarr_ids_map = RadarrService().get_all_tmdb_ids_map()
        sonarr_ids_map = SonarrService().get_all_tvdb_ids_map()
    else:
        # If passed from the caller, assume they are media server IDs
        media_server_ids = library_ids

    # Ensure all keys are strings for robust lookup
    media_server_ids = {str(k): v for k, v in media_server_ids.items()}
    radarr_ids_map = {str(k): v for k, v in radarr_ids_map.items()}
    sonarr_ids_map = {str(k): v for k, v in sonarr_ids_map.items()}

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
            in_media_server = tmdb_id in media_server_ids or tvdb_id in media_server_ids or member_title.lower() in media_server_ids
            
            radarr_id = radarr_ids_map.get(tmdb_id) if m_type == MediaType.MOVIE else None
            sonarr_id = sonarr_ids_map.get(tvdb_id) if m_type == MediaType.SHOW else None
            in_managers = (radarr_id is not None) or (sonarr_id is not None)
            
            in_library = in_media_server or in_managers
            
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
            
            is_downloaded = in_media_server

            gathered_candidates.append({
                'tmdb_id': tmdb_id,
                'media_type': m_type,
                'title': search_res.get('title') or search_res.get('name'),
                'overview': search_res.get('overview', ''),
                'poster_path': search_res.get('poster_path'),
                'imdb_id': imdb_id,
                'tvdb_id': tvdb_id,
                'radarr_id': radarr_id,
                'sonarr_id': sonarr_id,
                'imdb_rating': search_res.get('vote_average'),
                'runtime': avg_runtime,
                'content_rating': rating,
                'content_advisory': advisory,
                'streaming_providers': providers_str,
                'state': state,
                'is_downloaded': is_downloaded,
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
                    'is_downloaded': candidate['is_downloaded'],
                    'radarr_id': candidate.get('radarr_id'),
                    'sonarr_id': candidate.get('sonarr_id'),
                    'first_season_episodes': candidate.get('first_season_episodes'),
                    'tasting_episodes_count': candidate['tasting_episodes_count']
                }
            )
            from ...models.universe import Universe
            universe_obj, _ = Universe.objects.get_or_create(name=collection_name)
            show_obj.universes.add(universe_obj)

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
                defaults={
                    'title': candidate['title'],
                    'universe_name': collection_name,
                    'state': candidate['state'],
                    'is_downloaded': candidate['is_downloaded'],
                    'radarr_id': candidate.get('radarr_id'),
                    'sonarr_id': candidate.get('sonarr_id')
                }
            )
            from ...models.universe import Universe
            universe_obj, _ = Universe.objects.get_or_create(name=collection_name)
            show_obj.universes.add(universe_obj)

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
    Periodic maintenance task to ensure Vibarr's state matches Sonarr/Radarr and media servers.
    Detects when items are added/monitored in Sonarr/Radarr, heals their IDs, 
    accurately sets `is_downloaded` based on physical file availability in managers and media servers,
    and updates the UI state (e.g. SUGGESTED -> COMMITTED if added in manager).
    """
    logger.info("State Sync - Info - Starting external state sync with Sonarr, Radarr, and media servers.")
    
    sonarr = SonarrService()
    radarr = RadarrService()
    
    # 1. Fetch bulk data from managers and media servers
    all_sonarr_shows = sonarr.get_all_series_data()  # maps str(tvdbId) -> series dict
    all_radarr_movies = radarr.get_all_movies_data()  # maps str(tmdbId) -> movie dict
    
    media_server_ids = {}
    from ...utils.providers import get_active_providers
    providers = get_active_providers()
    for _, provider in providers:
        try:
            media_server_ids.update(provider.get_library_identifiers())
        except Exception as lib_err:
            logger.error(f"State Sync - Error - Failed to fetch library identifiers: {lib_err}")
            
    # Ensure all keys are strings for robust lookup
    media_server_ids = {str(k): v for k, v in media_server_ids.items()}
    
    # We want to sync status for all shows that are not rejected (Suggested, Tasting, Committed, Watched)
    shows = Show.objects.exclude(state=ShowState.REJECTED)
    
    for item in shows:
        try:
            in_media_server = str(item.tmdb_id) in media_server_ids or (item.tvdb_id and str(item.tvdb_id) in media_server_ids) or item.title.lower() in media_server_ids
            
            if item.media_type == MediaType.SHOW:
                tvdb_id_str = str(item.tvdb_id) if item.tvdb_id else None
                s_details = all_sonarr_shows.get(tvdb_id_str) if tvdb_id_str else None
                
                # If we don't have the TVDB ID mapped but we have the sonarr_id, try that
                if not s_details and item.sonarr_id:
                    s_details = next((s for s in all_sonarr_shows.values() if s.get('id') == item.sonarr_id), None)
                
                if s_details:
                    # Update manager ID if not set
                    if not item.sonarr_id:
                        item.sonarr_id = s_details['id']
                        
                    is_monitored = s_details.get('monitored', False)
                    
                    # If this was suggested but is added to Sonarr, promote it to COMMITTED
                    if item.state == ShowState.SUGGESTED:
                        logger.info(f"State Sync - Info - Show '{item.title}' detected in Sonarr. Promoting state to COMMITTED.")
                        item.state = ShowState.COMMITTED
                        
                    # Health Check: Monitoring Status for TASTING/COMMITTED
                    if item.state == ShowState.COMMITTED:
                        has_unmonitored_season = any(not s.get('monitored') for s in s_details.get('seasons', []))
                        if not is_monitored or has_unmonitored_season:
                            logger.info(f"State Sync - Info - Healing monitoring for committed show: {item.title} (Series: {is_monitored}, Seasons: {not has_unmonitored_season})")
                            sonarr.commit_series(item.sonarr_id)
                    
                    elif item.state == ShowState.TASTING:
                        if not is_monitored:
                            logger.info(f"State Sync - Info - Healing series-level monitoring for tasting show: {item.title}")
                            s_details['monitored'] = True
                            sonarr.update_series(s_details)
                            sonarr.monitor_episodes(item.sonarr_id, item.tasting_episodes_count)
                        else:
                            has_monitored_season = any(s.get('monitored') and s.get('seasonNumber') == 1 for s in s_details.get('seasons', []))
                            if not has_monitored_season:
                                logger.info(f"State Sync - Info - Healing season-level monitoring for tasting show: {item.title}")
                                sonarr.monitor_episodes(item.sonarr_id, item.tasting_episodes_count)

                    # Determine physical file status
                    stats = s_details.get('statistics', {})
                    episode_file_count = stats.get('episodeFileCount', 0)
                    item.is_downloaded = in_media_server or (episode_file_count > 0)
                    item.save()
                    
                else:
                    # If it has sonarr_id but not found in Sonarr, and state was active, it was deleted externally!
                    if item.sonarr_id and item.state in [ShowState.TASTING, ShowState.COMMITTED]:
                        logger.warning(f"State Sync - Warning - Show '{item.title}' (ID: {item.sonarr_id}) not found in Sonarr. Marking as REJECTED.")
                        item.state = ShowState.REJECTED
                        item.is_downloaded = False
                        item.save()
                    elif in_media_server:
                        if not item.is_downloaded:
                            item.is_downloaded = True
                            item.save()

            elif item.media_type == MediaType.MOVIE:
                tmdb_id_str = str(item.tmdb_id) if item.tmdb_id else None
                m_details = all_radarr_movies.get(tmdb_id_str) if tmdb_id_str else None
                
                # If we don't have the TMDB ID mapped but we have the radarr_id, try that
                if not m_details and item.radarr_id:
                    m_details = next((m for m in all_radarr_movies.values() if m.get('id') == item.radarr_id), None)
                
                if m_details:
                    # Update manager ID if not set
                    if not item.radarr_id:
                        item.radarr_id = m_details['id']
                        
                    # If this was suggested but is added to Radarr, promote it to COMMITTED
                    if item.state == ShowState.SUGGESTED:
                        logger.info(f"State Sync - Info - Movie '{item.title}' detected in Radarr. Promoting state to COMMITTED.")
                        item.state = ShowState.COMMITTED
                        
                    # Ensure it is monitored for committed
                    if item.state in [ShowState.TASTING, ShowState.COMMITTED] and not m_details.get('monitored'):
                        logger.info(f"State Sync - Info - Healing monitoring for movie in Radarr: {item.title}")
                        m_details['monitored'] = True
                        radarr.update_movie(m_details)
                        
                    item.is_downloaded = in_media_server or m_details.get('hasFile', False)
                    item.save()
                    
                else:
                    # If it has radarr_id but not found in Radarr, and state was active, it was deleted externally!
                    if item.radarr_id and item.state in [ShowState.TASTING, ShowState.COMMITTED]:
                        logger.warning(f"State Sync - Warning - Movie '{item.title}' (ID: {item.radarr_id}) not found in Radarr. Marking as REJECTED.")
                        item.state = ShowState.REJECTED
                        item.is_downloaded = False
                        item.save()
                    elif in_media_server:
                        if not item.is_downloaded:
                            item.is_downloaded = True
                            item.save()

        except Exception as e:
            logger.error(f"State Sync - Error - Error maintaining state for {item.title}: {e}")
            continue


def reevaluate_universe_shows(universe_name):
    """
    On-demand task to re-evaluate the recommendations scores for all suggested
    and tasting items belonging to a specific cinematic universe.
    """
    from ...tasks.discovery.recommendations import reevaluate_single_show

    shows = Show.objects.filter(universes__name=universe_name, state__in=[ShowState.SUGGESTED, ShowState.TASTING]).distinct()
    logger.info(f"Universe Architect - Info - Starting on-demand reanalysis for universe: '{universe_name}' ({shows.count()} items)")

    count = 0
    for show in shows:
        try:
            reevaluate_single_show(show)
            count += 1
        except Exception as e:
            logger.error(f"Universe Architect - Error - On-demand reanalysis failed for show '{show.title}': {e}")

    logger.info(f"Universe Architect - Info - Completed on-demand reanalysis for universe: '{universe_name}' (Processed {count}/{shows.count()} items)")


def analyze_universe_ecosystem_task():
    """
    Background task to analyze current universes and generate merge/alignment suggestions.
    """
    from ...models.universe import Universe, UniverseMergeSuggestion
    from ...services.discovery.ai_service import AIService
    from django.core.cache import cache
    
    logger.info("Universe Alignment - Info - Starting background AI ecosystem analysis.")
    cache.set('universe_scan_running', True, 300)
    cache.set('universe_scan_progress', 10, 300)
    cache.set('universe_scan_status', 'Gathering active universes...', 300)
    
    # 1. Gather all current universes that have items
    universes = Universe.objects.prefetch_related('shows').all()
    
    universes_data = []
    for universe in universes:
        items = []
        for show in universe.shows.all():
            items.append({
                "title": show.title,
                "type": show.media_type
            })
        if items:
            universes_data.append({
                "name": universe.name,
                "items": items
            })
            
    cache.set('universe_scan_progress', 30, 300)
    cache.set('universe_scan_status', f'Analyzing {len(universes_data)} universes with AI...', 300)
    
    if not universes_data:
        logger.info("Universe Alignment - Info - No universes to analyze.")
        UniverseMergeSuggestion.objects.all().delete()
        cache.set('universe_scan_progress', 100, 300)
        cache.set('universe_scan_status', 'Done. No universes to analyze.', 300)
        cache.set('universe_scan_running', False, 300)
        return
        
    try:
        ai = AIService()
        cache.set('universe_scan_progress', 50, 300)
        suggestions = ai.analyze_universe_ecosystem(universes_data)
        
        cache.set('universe_scan_progress', 75, 300)
        cache.set('universe_scan_status', 'Updating database alignment suggestions...', 300)
        
        from django.db import transaction
        with transaction.atomic():
            UniverseMergeSuggestion.objects.all().delete()
            
            created_count = 0
            for sug in suggestions:
                src_name = sug.get('source_universe')
                tgt_name = sug.get('target_universe')
                confidence = sug.get('confidence', 5)
                reasoning = sug.get('reasoning', '')
                
                if not src_name or not tgt_name or src_name == tgt_name:
                    continue
                    
                try:
                    src_univ = Universe.objects.get(name=src_name)
                    tgt_univ = Universe.objects.get(name=tgt_name)
                    
                    UniverseMergeSuggestion.objects.create(
                        source_universe=src_univ,
                        target_universe=tgt_univ,
                        confidence=confidence,
                        reasoning=reasoning
                    )
                    created_count += 1
                except Universe.DoesNotExist:
                    logger.warning(f"Universe Alignment - Warning - AI recommended merging '{src_name}' into '{tgt_name}', but one of them does not exist in DB.")
                    continue
                    
            logger.info(f"Universe Alignment - Info - Completed background AI analysis. Generated {created_count} suggestions.")
            cache.set('universe_scan_progress', 100, 300)
            cache.set('universe_scan_status', f'Scan complete! Generated {created_count} suggestions.', 300)
    except Exception as e:
        logger.error(f"Universe Alignment - Error - AI ecosystem analysis failed: {e}")
        cache.set('universe_scan_status', f'Scan failed: {str(e)}', 300)
        cache.set('universe_scan_progress', 100, 300)
    finally:
        cache.set('universe_scan_running', False, 300)

