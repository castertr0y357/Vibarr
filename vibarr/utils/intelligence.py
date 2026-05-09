from django.db.models import Max
from ..models import MediaWatchEvent, AppConfig, MediaType

def get_weighted_history_profile(target_type):
    """
    Builds a list of titles from history to feed the AI, 
    weighted by cross-media influence settings.
    """
    config = AppConfig.get_solo()
    
    if target_type == MediaType.MOVIE:
        primary_type = MediaType.MOVIE
        secondary_type = MediaType.SHOW
        influence_weight = config.show_influence_on_movies
    else:
        primary_type = MediaType.SHOW
        secondary_type = MediaType.MOVIE
        influence_weight = config.movie_influence_on_shows

    # Get Primary History (Full weight) - Unique titles ordered by latest watch
    primary_history = list(MediaWatchEvent.objects.filter(
        media_type=primary_type
    ).values('show_title').annotate(
        latest_watch=Max('watched_at')
    ).order_by('-latest_watch').values_list('show_title', flat=True)[:20])

    # Get Influencer History (Weighted subset)
    influence_count = max(1, int(20 * (influence_weight / 100)))
    influencer_history = list(MediaWatchEvent.objects.filter(
        media_type=secondary_type
    ).values('show_title').annotate(
        latest_watch=Max('watched_at')
    ).order_by('-latest_watch').values_list('show_title', flat=True)[:influence_count])

    return primary_history + influencer_history
