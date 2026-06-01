from django.db.models import Max, Count
from ..models import MediaWatchEvent, AppConfig, MediaType

def get_weighted_history_profile(target_type):
    """
    Builds a list of titles from history to feed the AI, 
    weighted by cross-media influence settings.
    Blends the top 10 most recent unique items and the top 10 overall most played items.
    Returns a list of dicts: [{'title': str, 'play_count': int, 'is_primary': bool}]
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

    # Get Primary History
    primary_events = MediaWatchEvent.objects.filter(
        media_type=primary_type
    ).values('show_title').annotate(
        latest_watch=Max('watched_at'),
        play_count=Count('id')
    )

    # Blended primary list: 10 recent, 10 top played
    primary_recent = list(primary_events.order_by('-latest_watch')[:10])
    primary_top = list(primary_events.order_by('-play_count', '-latest_watch')[:10])

    seen_titles = set()
    primary_history = []
    
    # Add recent first to preserve recent order at the front of the list
    for e in primary_recent:
        title = e['show_title']
        if title not in seen_titles:
            seen_titles.add(title)
            primary_history.append({'title': title, 'play_count': e['play_count'], 'is_primary': True})

    for e in primary_top:
        title = e['show_title']
        if title not in seen_titles:
            seen_titles.add(title)
            primary_history.append({'title': title, 'play_count': e['play_count'], 'is_primary': True})

    # Get Influencer History (Weighted subset)
    influence_count = max(1, int(20 * (influence_weight / 100)))
    influencer_events = MediaWatchEvent.objects.filter(
        media_type=secondary_type
    ).values('show_title').annotate(
        latest_watch=Max('watched_at'),
        play_count=Count('id')
    )

    recent_count = max(1, influence_count // 2)
    top_count = max(1, influence_count - recent_count)

    influencer_recent = list(influencer_events.order_by('-latest_watch')[:recent_count])
    influencer_top = list(influencer_events.order_by('-play_count', '-latest_watch')[:top_count])

    seen_inf_titles = set()
    influencer_history = []
    
    for e in influencer_recent:
        title = e['show_title']
        if title not in seen_inf_titles:
            seen_inf_titles.add(title)
            influencer_history.append({'title': title, 'play_count': e['play_count'], 'is_primary': False})

    for e in influencer_top:
        title = e['show_title']
        if title not in seen_inf_titles:
            seen_inf_titles.add(title)
            influencer_history.append({'title': title, 'play_count': e['play_count'], 'is_primary': False})

    return primary_history + influencer_history

def get_recent_history_profile(target_type, limit=5):
    """
    Returns the last `limit` unique watched items with titles and tmdb_ids.
    """
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


