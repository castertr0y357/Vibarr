import logging
from django.utils import timezone
from django.core.cache import cache
from django_q.tasks import async_task
from django.db.models import Q

from ...models import Show, Recommendation, MediaWatchEvent, ShowState, MediaType, AppConfig
from ...models.enums import RATING_SCALE
from ...services.discovery.tmdb_service import TMDBService
from ...services.discovery.ai_service import AIService
from ...services.discovery.heuristic_ranking import HeuristicRankingService
from ...utils.providers import get_active_providers
from ...utils.intelligence import get_weighted_history_profile
from ...services.managers.sonarr_service import SonarrService
from ...services.managers.radarr_service import RadarrService
import time

logger = logging.getLogger(__name__)

def get_tasting_count(runtime):
    config = AppConfig.objects.first()
    default_count = config.default_tasting_count if config else 3
    if not runtime: return default_count
    if runtime < 35: return default_count + 2
    return default_count


def refresh_discovery_tracks():
    """
    Background job to proactively fill the discovery backlogs for both tracks.
    """
    config = AppConfig.get_solo()
    tmdb = TMDBService()
    
    # 1. Refresh Movies
    current_movies = Show.objects.filter(state=ShowState.SUGGESTED, media_type=MediaType.MOVIE).count()
    if current_movies < config.max_discovered_movies:
        needed = config.max_discovered_movies - current_movies
        logger.info(f"[AI Scout] Movie backlog at {current_movies}/{config.max_discovered_movies}. Refreshing...")
        scout_for_media_type(MediaType.MOVIE, limit=min(needed, 10))

    # 2. Refresh Shows
    current_shows = Show.objects.filter(state=ShowState.SUGGESTED, media_type=MediaType.SHOW).count()
    if current_shows < config.max_discovered_shows:
        needed = config.max_discovered_shows - current_shows
        logger.info(f"[AI Scout] Show backlog at {current_shows}/{config.max_discovered_shows}. Refreshing...")
        scout_for_media_type(MediaType.SHOW, limit=min(needed, 10))

def scout_for_media_type(target_type, limit=5):
    """
    Finds and ranks new recommendations specifically for a media type.
    """
    tmdb = TMDBService()
    ai = AIService()
    config = AppConfig.get_solo()

    # Build the weighted profile
    profile = get_weighted_history_profile(target_type)
    if not profile:
        logger.warning(f"[AI Scout] No history found to scout for {target_type}. Skipping.")
        return

    # Pick a seed from history to get similar candidates from TMDB
    seed_title = profile[0]
    is_movie = target_type == MediaType.MOVIE
    
    search_result = tmdb.search_movie(seed_title) if is_movie else tmdb.search_show(seed_title)
    if not search_result: return

    tmdb_id = search_result['id']
    if is_movie:
        candidates_raw = tmdb.get_similar_movies(tmdb_id)[:40]
        for c in candidates_raw: c['_media_type'] = MediaType.MOVIE
    else:
        candidates_raw = tmdb.get_similar_shows(tmdb_id)[:40]
        for c in candidates_raw: c['_media_type'] = MediaType.SHOW

    # Filter candidates
    library_titles = set()
    for _, provider in get_active_providers():
        library_titles.update([t.lower() for t in provider.get_library_titles()])

    candidates = []
    for c in candidates_raw:
        title_lower = (c.get('name') or c.get('title', '')).lower()
        if Show.objects.filter(tmdb_id=c['id'], media_type=target_type).exists(): continue
        if MediaWatchEvent.objects.filter(tmdb_id=c['id'], media_type=target_type).exists(): continue
        if title_lower in library_titles: continue
        
        candidates.append({
            'id': c['id'],
            'title': c.get('name') or c.get('title'),
            'overview': c.get('overview', ''),
            'poster_path': c.get('poster_path'),
            'vote_average': c.get('vote_average', 0),
            'vote_count': c.get('vote_count', 0),
            'popularity': c.get('popularity', 0),
            'genre_ids': c.get('genre_ids', []),
            '_media_type': target_type
        })

    if not candidates: return

    # Reranking
    now = timezone.now()
    context = "Weekend" if now.weekday() >= 5 else "Weekday"
    
    if config.use_ai_recommendations:
        ai = AIService()
        ranked_results = ai.rank_shows(profile, candidates, context=context)
    else:
        hrs = HeuristicRankingService(config)
        ranked_results = hrs.rank_candidates(target_type, candidates)

    # Process Top Results
    current_tasting = Show.objects.filter(state=ShowState.TASTING).count()
    
    for ranked in ranked_results[:limit]:
        match = next((c for c in candidates if c['title'].lower() == ranked['title'].lower()), None)
        if not match: continue

        details = tmdb.get_movie_details(match['id']) if is_movie else tmdb.get_show_details(match['id'])
        if not details: continue
        
        imdb_id = details.get('external_ids', {}).get('imdb_id')
        tvdb_id = details.get('external_ids', {}).get('tvdb_id')
        avg_runtime = details.get('episode_run_time', [0])[0] if details.get('episode_run_time') else details.get('runtime', 120)
        rating, advisory = tmdb.parse_advisory(details, is_movie=is_movie)
        
        show, created = Show.objects.get_or_create(
            tmdb_id=match['id'],
            media_type=target_type,
            defaults={
                'title': match['title'],
                'poster_path': match['poster_path'],
                'imdb_id': imdb_id,
                'tvdb_id': tvdb_id,
                'imdb_rating': match['vote_average'], # Fallback to TMDB rating
                'runtime': avg_runtime,
                'content_rating': rating,
                'content_advisory': advisory,
                'streaming_providers': ", ".join(tmdb.get_watch_providers(match['id'], is_movie=is_movie)),
                'tasting_episodes_count': 1 if is_movie else get_tasting_count(avg_runtime),
                'state': ShowState.SUGGESTED
            }
        )
        
        ai_score = ranked.get('score', match['vote_average'])
        Recommendation.objects.get_or_create(
            suggested_show=show,
            defaults={
                'source_title': seed_title,
                'score': ai_score,
                'reasoning': ranked.get('reasoning', "Matches weighted viewing habits."),
                'vibe_tags': ", ".join(ranked.get('vibe_tags', [])) if isinstance(ranked.get('vibe_tags'), list) else ""
            }
        )

        # Auto-Tasting
        if ai_score >= config.auto_tasting_threshold and current_tasting < config.max_tasting_items:
            logger.info(f"[AI Scout] High confidence match ({ai_score}) for '{show.title}'. Starting Auto-Tasting.")
            async_task('vibarr.tasks.managers.actions.start_tasting', show.id)
            current_tasting += 1

def generate_recommendations(title, is_movie=False):
    """
    Legacy wrapper for reactive scouting, now respects new governance.
    """
    target_type = MediaType.MOVIE if is_movie else MediaType.SHOW
    scout_for_media_type(target_type, limit=5)

def refresh_metadata_backlog(full_sweep=False):
    """
    Backfills missing IMDB IDs and refreshes ratings for existing suggestions.
    """
    tmdb = TMDBService()
    
    # Target items missing IMDB or TVDB IDs first, then stale ones
    count = 0
    query = Show.objects.filter(
        Q(imdb_id__isnull=True) | Q(tvdb_id__isnull=True)
    ).exclude(state=ShowState.REJECTED).order_by('-created_at')
    
    if not full_sweep:
        query = query[:25]
    
    legacy_items = list(query)
    
    if not legacy_items and not full_sweep:
        # If all IDs are present and not a full sweep, refresh the oldest 10 ratings
        legacy_items = list(Show.objects.exclude(
            state=ShowState.REJECTED
        ).order_by('updated_at')[:10])
    elif full_sweep:
        # For a full sweep, if we have no missing IDs, we refresh EVERYTHING that isn't rejected
        if not legacy_items:
            legacy_items = list(Show.objects.exclude(state=ShowState.REJECTED).order_by('updated_at'))

    sonarr = SonarrService()
    radarr = RadarrService()
    
    for show in legacy_items:
        try:
            is_movie = show.media_type == MediaType.MOVIE
            details = tmdb.get_movie_details(show.tmdb_id) if is_movie else tmdb.get_show_details(show.tmdb_id)
            
            if details:
                # Update metadata from TMDB (Option 1)
                show.imdb_id = details.get('external_ids', {}).get('imdb_id')
                show.tvdb_id = details.get('external_ids', {}).get('tvdb_id', show.tvdb_id)
                show.imdb_rating = details.get('vote_average', show.imdb_rating)
                show.streaming_providers = ", ".join(tmdb.get_watch_providers(show.tmdb_id, is_movie=is_movie))
            
            # Option 2: Enrichment via Manager Proxy (Sonarr/Radarr)
            if is_movie and show.radarr_id:
                m_details = radarr.get_movie(show.radarr_id)
                if m_details:
                    show.imdb_id = m_details.get('imdbId', show.imdb_id)
                    show.tmdb_id = m_details.get('tmdbId', show.tmdb_id)
            
            elif not is_movie and show.sonarr_id:
                s_details = sonarr.get_series(show.sonarr_id)
                if s_details:
                    show.tvdb_id = s_details.get('tvdbId', show.tvdb_id)
                    if s_details.get('ratings', {}).get('value'):
                        show.imdb_rating = s_details['ratings']['value']

            show.save()
            count += 1
            
            # Rate limiting breather for full sweeps
            if full_sweep:
                time.sleep(0.25)
        except Exception as e:
            logger.error(f"[Metadata Sync] Maintenance Error on '{show.title}': {e}")
            continue
        
    logger.info(f"[Metadata Sync] Refreshed {count} items.")
    return count

def revaluate_all_recommendations():
    """
    Periodically refreshes the scores of all active discoveries and tastings 
    based on the latest watch history.
    """
    config = AppConfig.get_solo()
    ai = AIService()
    
    # We re-evaluate SUGGESTED and TASTING items
    items_to_score = Show.objects.filter(
        state__in=[ShowState.SUGGESTED, ShowState.TASTING]
    ).order_by('-updated_at')
    
    if not items_to_score.exists():
        return
        
    logger.info(f"[AI Re-evaluator] Starting re-evaluation of {items_to_score.count()} items.")
    
    # Build history profiles (we'll need both for broad context)
    movie_profile = get_weighted_history_profile(MediaType.MOVIE)
    show_profile = get_weighted_history_profile(MediaType.SHOW)
    full_profile = list(set(movie_profile + show_profile))

    # Batch process 15 items at a time
    items_list = list(items_to_score)
    updated_count = 0
    promoted_count = 0
    
    for i in range(0, len(items_list), 15):
        batch = items_list[i:i+15]
        candidates = []
        for item in batch:
            # We need title and overview for the AI
            # We'll try to find an existing recommendation to get source_title or just use title
            candidates.append({
                'title': item.title,
                'overview': item.recommendations.first().reasoning if item.recommendations.exists() else ""
            })
            
        if config.use_ai_recommendations:
            scores = ai.score_candidates(full_profile, candidates)
        else:
            hrs = HeuristicRankingService(config)
            # hrs.rank_candidates returns the same format as ai.score_candidates mostly
            # but we need to pass the target_type which might be mixed here.
            # For simplicity in re-evaluation, we'll use the item's own media_type.
            scores = []
            for item, cand in zip(batch, candidates):
                scores.append(hrs._calculate_score(cand, item.media_type, 
                                                hrs._build_user_profile(item.media_type), 
                                                hrs._build_seerr_profile() if config.use_seerr else set()))

        scores_map = {s['title'].lower(): s for s in scores}
        
        for item in batch:
            ai_data = scores_map.get(item.title.lower())
            if not ai_data: continue
            
            new_score = ai_data.get('score', 0)
            new_reasoning = ai_data.get('reasoning', "Matches updated viewing habits.")
            new_tags = ", ".join(ai_data.get('vibe_tags', [])) if isinstance(ai_data.get('vibe_tags'), list) else ""
            
            # Update Recommendation
            rec = item.recommendations.first()
            if rec:
                rec.score = new_score
                rec.reasoning = new_reasoning
                rec.vibe_tags = new_tags
                rec.save()
                updated_count += 1
                
                # Check for Auto-Tasting promotion
                if item.state == ShowState.SUGGESTED and new_score >= config.auto_tasting_threshold:
                    current_tasting = Show.objects.filter(state=ShowState.TASTING).count()
                    if current_tasting < config.max_tasting_items:
                        logger.info(f"[AI Re-evaluator] Item '{item.title}' score increased to {new_score}. Promoting to Auto-Tasting.")
                        async_task('vibarr.tasks.managers.actions.start_tasting', item.id)
                        promoted_count += 1

    logger.info(f"[AI Re-evaluator] Finished. Updated {updated_count} scores, Promoted {promoted_count} items.")
