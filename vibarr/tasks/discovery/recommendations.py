from ...models import Show, Recommendation, MediaWatchEvent, ShowState, MediaType, AppConfig
from ...services.discovery.tmdb_service import TMDBService
from ...services.discovery.ai_service import AIService
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

def get_tasting_count(runtime):
    config = AppConfig.objects.first()
    default_count = config.default_tasting_count if config else 3
    if not runtime: return default_count
    if runtime < 35: return default_count + 2
    return default_count

def generate_recommendations(title, is_movie=False, library_titles=None):
    # Debounce: Don't re-run for the same title within 24 hours
    from django.core.cache import cache
    cache_key = f"scout_debounce_{title.lower()}"
    if cache.get(cache_key):
        logger.info(f"Skipping redundant recommendation for '{title}' (debounced by cache).")
        return
    cache.set(cache_key, True, 86400) # 24 hours

    tmdb = TMDBService()
    ai = AIService()
    config = AppConfig.get_solo()
    
    search_result = tmdb.search_movie(title) if is_movie else tmdb.search_show(title)
    if not search_result: return

    tmdb_id = search_result['id']
    if is_movie:
        similar = tmdb.get_similar_movies(tmdb_id)[:30]
        for c in similar: c['_media_type'] = MediaType.MOVIE
        cross = tmdb.get_cross_recommendations(tmdb_id, source_is_movie=True)[:20]
        for c in cross: c['_media_type'] = MediaType.SHOW
        candidates_raw = similar + cross
    else:
        similar = tmdb.get_similar_shows(tmdb_id)[:30]
        for c in similar: c['_media_type'] = MediaType.SHOW
        cross = tmdb.get_cross_recommendations(tmdb_id, source_is_movie=False)[:20]
        for c in cross: c['_media_type'] = MediaType.MOVIE
        candidates_raw = similar + cross
        
    if library_titles is None:
        from ..media.polling import get_active_providers
        library_titles = []
        for _, provider in get_active_providers():
            library_titles.extend([t.lower() for t in provider.get_library_titles()])
        library_titles = list(set(library_titles))

    genre_map = tmdb.get_genre_list(is_movie=is_movie)
    active_persona = config.active_persona
    
    # Combine Blacklists
    global_blacklist = [g.strip().lower() for g in config.ignored_genres.split(',')] if config and config.ignored_genres else []
    persona_blacklist = [g.strip().lower() for g in active_persona.ignored_genres.split(',')] if active_persona and active_persona.ignored_genres else []
    ignored_genres = list(set(global_blacklist + persona_blacklist))

    from ...models.enums import RATING_SCALE
    if active_persona:
        max_rating_val = RATING_SCALE.get(active_persona.max_content_rating, 10)
    else:
        max_rating_val = RATING_SCALE.get(config.max_content_rating, 10)

    candidates = []
    for c in candidates_raw:
        title_lower = (c.get('name') or c.get('title', '')).lower()
        if Show.objects.filter(tmdb_id=c['id']).exists(): continue
        if MediaWatchEvent.objects.filter(tmdb_id=c['id']).exists(): continue
        if library_titles and title_lower in library_titles: continue
            
        # Genre Blacklist Check
        if ignored_genres:
            item_genres = [genre_map.get(gid, '').lower() for gid in c.get('genre_ids', [])]
            if any(ig in item_genres for ig in ignored_genres): continue
        
        candidates.append({
            'id': c['id'],
            'title': c.get('name') or c.get('title'),
            'overview': c.get('overview', ''),
            'poster_path': c.get('poster_path'),
            'vote_average': c.get('vote_average', 0),
            'genre_ids': c.get('genre_ids', []),
            '_media_type': c.get('_media_type')
        })

    if not candidates: return

    recent_history = MediaWatchEvent.objects.order_by('-watched_at').values_list('show_title', flat=True).distinct()[:20]
    
    if config and not config.use_ai_recommendations:
        # Heuristic Mode
        ranked_results = []
        for c in sorted(candidates, key=lambda x: x['vote_average'], reverse=True)[:5]:
            item_genres = [genre_map.get(gid, '') for gid in c.get('genre_ids', [])] if 'genre_ids' in c else []
            ranked_results.append({
                'title': c['title'],
                'reasoning': f"Popular matching title based on your interest in '{title}'.",
                'score': c['vote_average'],
                'vibe_tags': item_genres[:3]
            })
    else:
        # AI Mode
        now = timezone.now()
        context = "Weekend" if now.weekday() >= 5 else "Weekday"
        ranked_results = ai.rank_shows(list(recent_history), candidates, context=context)
    
    from ..managers.actions import start_tasting
    for ranked in ranked_results[:5]: 
        match = next((c for c in candidates if c['title'].lower() == ranked['title'].lower()), None)
        if not match: continue
            
        is_candidate_movie = match['_media_type'] == MediaType.MOVIE
        details = tmdb.get_movie_details(match['id']) if is_candidate_movie else tmdb.get_show_details(match['id'])
        if not details: continue
        
        avg_runtime = details.get('episode_run_time', [0])[0] if details.get('episode_run_time') else details.get('runtime', 120)
        rating, advisory = tmdb.parse_advisory(details, is_movie=is_candidate_movie)
        
        # Household Lens: Detailed Rating Check
        if active_persona:
            item_rating_val = RATING_SCALE.get(rating, 4) # Default to R-ish for safety
            if item_rating_val > max_rating_val:
                logger.info(f"Skipping '{match['title']}' - rating {rating} exceeds Persona limit {active_persona.rating_limit}")
                continue

        show, created = Show.objects.get_or_create(
            tmdb_id=match['id'],
            media_type=match['_media_type'],
            defaults={
                'title': match['title'],
                'poster_path': match['poster_path'],
                'runtime': avg_runtime,
                'content_rating': rating,
                'content_advisory': advisory,
                'streaming_providers': ", ".join(tmdb.get_watch_providers(match['id'], is_movie=is_candidate_movie)),
                'tasting_episodes_count': 1 if is_candidate_movie else get_tasting_count(avg_runtime),
                'state': ShowState.SUGGESTED
            }
        )
        
        ai_score = ranked.get('score', match['vote_average'])
        Recommendation.objects.get_or_create(
            suggested_show=show,
            defaults={
                'source_title': title,
                'score': ai_score,
                'reasoning': ranked.get('reasoning', "Matches viewing habits."),
                'vibe_tags': ", ".join(ranked.get('vibe_tags', [])) if isinstance(ranked.get('vibe_tags'), list) else ""
            }
        )

        # Autonomous Tasting Check
        if config and ai_score >= config.auto_tasting_threshold:
            logger.info(f"Autonomous Scout: High confidence match ({ai_score}/10) for '{show.title}'. Starting Tasting.")
            from django_q.tasks import async_task
            async_task(start_tasting, show.id)
