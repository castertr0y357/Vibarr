import logging
from ..models import AppConfig, MediaServerType
from ..services.media.plex_service import PlexService
from ..services.media.jellyfin_service import JellyfinService

logger = logging.getLogger(__name__)

def get_active_providers():
    config = AppConfig.get_solo()
    providers = []
    if config.media_server_type in [MediaServerType.PLEX, MediaServerType.BOTH]:
        providers.append(('PLEX', PlexService()))
    if config.media_server_type in [MediaServerType.JELLYFIN, MediaServerType.BOTH]:
        providers.append(('JELLYFIN', JellyfinService()))
    return providers
