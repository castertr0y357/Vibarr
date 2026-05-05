from ...models import Show, Recommendation, ShowState, MediaType
from ...services.discovery.ai_service import AIService
from ...services.discovery.tmdb_service import TMDBService
from ...services.managers.sonarr_service import SonarrService
from ...services.managers.radarr_service import RadarrService
from ..media.polling import get_active_providers
import logging

logger = logging.getLogger(__name__)

def discover_universe_and_sync(show_id, library_titles=None):
    try:
        show = Show.objects.get(id=show_id)
    except Show.DoesNotExist:
        return
        
    ai = AIService()
    providers = get_active_providers()
    
    universe = ai.identify_universe(show.title)
    if not universe.get('universe_name'): return
        
    collection_name = universe['universe_name']
    members = universe['members']
    
    for _, provider in providers:
        provider.sync_collection(members, collection_name)
    
    if library_titles is None:
        library_titles = []
        for _, provider in providers:
            library_titles.extend([t.lower() for t in provider.get_library_titles()])

    tmdb = TMDBService()
    for member_title in members:
        if member_title.lower() in library_titles: continue
        search_res = tmdb.search_movie(member_title) or tmdb.search_show(member_title)
        if search_res:
            m_type = MediaType.MOVIE if 'title' in search_res else MediaType.SHOW
            new_show, created = Show.objects.get_or_create(
                tmdb_id=search_res['id'],
                defaults={'title': search_res.get('title') or search_res.get('name'), 'media_type': m_type, 'state': ShowState.SUGGESTED}
            )
            Recommendation.objects.get_or_create(
                suggested_show=new_show,
                defaults={'source_title': show.title, 'score': 10.0, 'reasoning': f"Part of {collection_name}.", 'vibe_tags': "Universe"}
            )
    
    from ...services.comms.notification_service import NotificationService
    NotificationService().notify_universe_found(show.title, collection_name, len(members))

def batch_universe_sync():
    """Batches universe discovery for all committed shows."""
    committed = Show.objects.filter(state=ShowState.COMMITTED)
    providers = get_active_providers()
    library_titles = []
    for _, provider in providers:
        library_titles.extend([t.lower() for t in provider.get_library_titles()])
    
    for show in committed:
        discover_universe_and_sync(show.id, library_titles=library_titles)

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
        except Exception: pass
