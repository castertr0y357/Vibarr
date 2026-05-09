from django.db import models

class ShowState(models.TextChoices):
    SUGGESTED = 'SUGGESTED', 'Suggested'
    TASTING = 'TASTING', 'Tasting'
    COMMITTED = 'COMMITTED', 'Committed'
    REJECTED = 'REJECTED', 'Rejected'
    WATCHED = 'WATCHED', 'Watched'

class MediaType(models.TextChoices):
    SHOW = 'SHOW', 'Show'
    MOVIE = 'MOVIE', 'Movie'

class MediaServerType(models.TextChoices):
    PLEX = 'PLEX', 'Plex'
    JELLYFIN = 'JELLYFIN', 'Jellyfin'
    BOTH = 'BOTH', 'Plex & Jellyfin'

class AuthMode(models.TextChoices):
    NONE = 'NONE', 'None'
    EXTERNAL = 'EXTERNAL', 'External IPs Only'
    ALWAYS = 'ALWAYS', 'Always'

RATING_SCALE = {
    'G': 1, 'TV-G': 1, 
    'PG': 2, 'TV-PG': 2, 
    'PG-13': 3, 'TV-14': 3, 
    'R': 4, 'TV-MA': 4, 
    'NC-17': 5,
    'NR': 0, 'UR': 0
}
