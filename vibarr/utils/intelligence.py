from django.db.models import Max, Count
from ..models import MediaWatchEvent, AppConfig, MediaType

def get_weighted_history_profile(target_type):
    """
    Builds a list of titles from history to feed the AI, 
    weighted by cross-media influence settings.
    Returns a list of dicts: [{'title': str, 'play_count': int}]
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
    primary_events = MediaWatchEvent.objects.filter(
        media_type=primary_type
    ).values('show_title').annotate(
        latest_watch=Max('watched_at'),
        play_count=Count('id')
    ).order_by('-latest_watch')[:20]

    primary_history = [
        {'title': e['show_title'], 'play_count': e['play_count']}
        for e in primary_events
    ]

    # Get Influencer History (Weighted subset)
    influence_count = max(1, int(20 * (influence_weight / 100)))
    influencer_events = MediaWatchEvent.objects.filter(
        media_type=secondary_type
    ).values('show_title').annotate(
        latest_watch=Max('watched_at'),
        play_count=Count('id')
    ).order_by('-latest_watch')[:influence_count]

    influencer_history = [
        {'title': e['show_title'], 'play_count': e['play_count']}
        for e in influencer_events
    ]

    return primary_history + influencer_history

def get_recent_history_profile(target_type, limit=5):
    """
    Returns the last `limit` unique watched items with titles and tmdb_ids.
    """
    from django.db.models import Max
    from ..models import MediaWatchEvent
    
    events = MediaWatchEvent.objects.filter(
        media_type=target_type,
        tmdb_id__isnull=False
    ).values('show_title', 'tmdb_id').annotate(
        latest_watch=Max('watched_at')
    ).order_by('-latest_watch')[:limit]
    
    return [
        {'title': e['show_title'], 'tmdb_id': e['tmdb_id']}
        for e in events
    ]

def get_core_history_profile(target_type, limit=30):
    """
    Returns the top unique titles by play count, including cross-media influence.
    """
    from django.db.models import Max, Count
    from ..models import MediaWatchEvent, AppConfig, MediaType
    
    config = AppConfig.get_solo()
    
    if target_type == MediaType.MOVIE:
        primary_type = MediaType.MOVIE
        secondary_type = MediaType.SHOW
        influence_weight = config.show_influence_on_movies
    else:
        primary_type = MediaType.SHOW
        secondary_type = MediaType.MOVIE
        influence_weight = config.movie_influence_on_shows
        
    primary_events = MediaWatchEvent.objects.filter(
        media_type=primary_type
    ).values('show_title', 'tmdb_id').annotate(
        latest_watch=Max('watched_at'),
        play_count=Count('id')
    ).order_by('-play_count', '-latest_watch')[:limit]
    
    primary_list = [
        {'title': e['show_title'], 'tmdb_id': e['tmdb_id'], 'play_count': e['play_count']}
        for e in primary_events
    ]
    
    influence_limit = max(1, int(limit * (influence_weight / 100)))
    influence_events = MediaWatchEvent.objects.filter(
        media_type=secondary_type
    ).values('show_title', 'tmdb_id').annotate(
        latest_watch=Max('watched_at'),
        play_count=Count('id')
    ).order_by('-play_count', '-latest_watch')[:influence_limit]
    
    influence_list = [
        {'title': e['show_title'], 'tmdb_id': e['tmdb_id'], 'play_count': e['play_count']}
        for e in influence_events
    ]
    
    # Merge and sort by play count
    combined = primary_list + influence_list
    combined.sort(key=lambda x: x['play_count'], reverse=True)
    return combined


