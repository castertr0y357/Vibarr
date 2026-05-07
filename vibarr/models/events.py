from django.db import models
from .enums import MediaServerType, MediaType
from .shows import Show

class MediaWatchEvent(models.Model):
    event_id = models.CharField(max_length=100, unique=True)
    source_server = models.CharField(
        max_length=10, 
        choices=MediaServerType.choices, 
        default=MediaServerType.PLEX
    )
    media_type = models.CharField(
        max_length=10,
        choices=MediaType.choices,
        default=MediaType.SHOW,
        db_index=True
    )
    tmdb_id = models.IntegerField(null=True, blank=True, db_index=True)
    show = models.ForeignKey(Show, on_delete=models.SET_NULL, null=True, blank=True)
    show_title = models.TextField(db_index=True)
    season = models.IntegerField()
    episode = models.IntegerField()
    watched_at = models.DateTimeField(db_index=True)
    
    # Progress tracking (for movies/partial views)
    view_offset = models.IntegerField(null=True, blank=True, help_text="Last watch position in milliseconds")
    duration = models.IntegerField(null=True, blank=True, help_text="Total duration in milliseconds")
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.source_server}] {self.show_title} S{self.season:02d}E{self.episode:02d}"
