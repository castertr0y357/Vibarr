import logging
import random
from django.utils import timezone
from django.core.cache import cache
from django_q.tasks import async_task

from ...models import Show, ShowState, MediaType, MediaWatchEvent, Recommendation
from ...services.discovery.ai_service import AIService
from ...services.discovery.tmdb_service import TMDBService
from ...services.comms.notification_service import NotificationService
from .recommendations import generate_recommendations
from ...utils.providers import get_active_providers

logger = logging.getLogger(__name__)


def run_bridge_check(show_id):
    """Triggered after a show/movie is committed or finished."""
    show = Show.objects.get(id=show_id)
    logger.info(f"Checking for cross-media bridge for: {show.title}")
    
    ai = AIService()
    bridge = ai.identify_cross_media_bridge(show.title, show.media_type)
    
    if bridge.get('title'):
        # Check if already owned/watched
        if Show.objects.filter(title__iexact=bridge['title']).exists():
             logger.info(f"Bridge target '{bridge['title']}' already exists. Skipping.")
             return
             
        tmdb = TMDBService()
        is_movie = bridge['media_type'] == 'MOVIE'
        search_res = tmdb.search_movie(bridge['title']) if is_movie else tmdb.search_show(bridge['title'])
        
        if search_res:
            details = tmdb.get_movie_details(search_res['id']) if is_movie else tmdb.get_show_details(search_res['id'])
            rating, advisory = tmdb.parse_advisory(details, is_movie=is_movie)
            
            new_show = Show.objects.create(
                title=bridge['title'],
                tmdb_id=search_res['id'],
                media_type=MediaType.MOVIE if is_movie else MediaType.SHOW,
                poster_path=search_res.get('poster_path'),
                content_rating=rating,
                content_advisory=advisory,
                state=ShowState.SUGGESTED
            )
            
            Recommendation.objects.create(
                suggested_show=new_show,
                source_title=show.title,
                reasoning=bridge['reasoning'],
                vibe_tags="Bridge"
            )
            
            notifier = NotificationService()
            notifier.send_message(
                f"🌉 <b>Bridge Found!</b> Since you enjoyed <b>{show.title}</b>, you should check out its {bridge['media_type'].lower()} counterpart: <b>{new_show.title}</b>.",
                title="Bridge Architected"
            )
            
            # Don't auto-start tasting for bridges, just suggest? 
            # Actually, the user liked the first one enough to commit, so auto-tasting is good.
            async_task('vibarr.tasks.managers.actions.start_tasting', new_show.id)

def background_scout():
    """Periodic task to scan history and find new matches."""
    # Get all unique titles from history
    all_titles = list(MediaWatchEvent.objects.values('show_title', 'media_type').distinct())
    
    # Priority 1: Recent history (watched in last 24h)
    since = timezone.now() - timezone.timedelta(days=1)
    recent_qs = MediaWatchEvent.objects.filter(watched_at__gt=since).values_list('show_title', flat=True)
    recent_titles_set = set(recent_qs)
    
    recent_titles = [t for t in all_titles if t['show_title'] in recent_titles_set]
    historical_titles = [t for t in all_titles if t['show_title'] not in recent_titles_set]
    
    candidates = []
    
    # Add un-scouted recent titles first
    for t in recent_titles:
        cache_key = f"scout_debounce_{t['show_title'].lower()}"
        if not cache.get(cache_key):
            candidates.append(t)
            
    # Backfill with un-scouted historical titles (batch size of 5 per run)
    if len(candidates) < 5 and historical_titles:
        random.shuffle(historical_titles)
        for t in historical_titles:
            if len(candidates) >= 5:
                break
            cache_key = f"scout_debounce_{t['show_title'].lower()}"
            if not cache.get(cache_key):
                candidates.append(t)
    
    for event in candidates:
        generate_recommendations(
            event['show_title'], 
            is_movie=(event['media_type'] == MediaType.MOVIE)
        )

