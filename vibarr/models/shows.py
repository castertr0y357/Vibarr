from django.db import models
from .enums import ShowState, MediaType
from .config import AppConfig

class Show(models.Model):
    title = models.TextField()
    tmdb_id = models.IntegerField(db_index=True)
    media_type = models.CharField(
        max_length=10,
        choices=MediaType.choices,
        default=MediaType.SHOW,
        db_index=True
    )
    sonarr_id = models.IntegerField(null=True, blank=True)
    radarr_id = models.IntegerField(null=True, blank=True)
    poster_path = models.TextField(null=True, blank=True)
    runtime = models.IntegerField(null=True, blank=True, help_text="Average episode runtime in minutes")
    content_rating = models.TextField(null=True, blank=True)
    content_advisory = models.TextField(null=True, blank=True, help_text="Keywords like Violence, Nudity, etc.")
    state = models.CharField(
        max_length=50,
        choices=ShowState.choices,
        default=ShowState.SUGGESTED,
        db_index=True
    )
    is_pinned = models.BooleanField(default=False, db_index=True)
    has_notified_ready = models.BooleanField(default=False)
    tasting_episodes_count = models.IntegerField(default=3, help_text="Number of episodes to download for tasting")
    streaming_providers = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['tmdb_id', 'media_type'], name='unique_tmdb_id_media_type')
        ]

    def __str__(self):
        return self.title

    @property
    def is_above_threshold(self):
        config = AppConfig.get_solo()
        if not config or not self.content_rating:
            return False
            
        from .enums import RATING_SCALE
        current = RATING_SCALE.get(self.content_rating, 0)
        
        # Priority: Active Persona > Global Config
        if config.active_persona:
            max_allowed = RATING_SCALE.get(config.active_persona.max_content_rating, 3)
        else:
            max_allowed = RATING_SCALE.get(config.max_content_rating, 3)
            
        return current > max_allowed

    @property
    def tasting_progress_percent(self):
        if self.media_type == MediaType.MOVIE:
            # Use all() to leverage prefetch_related if available
            events = self.mediawatchevent_set.all()
            if not events: return 0
            event = events[len(events)-1] # Equivalent to last() but uses cache
            if event.duration:
                return min(100, int((event.view_offset / event.duration) * 100))
            return 0
        else:
            # Use all() to leverage prefetch_related if available
            watched_events = self.mediawatchevent_set.all()
            unique_episodes = set((e.season, e.episode) for e in watched_events)
            watched = len(unique_episodes)
            return min(100, int((watched / self.tasting_episodes_count) * 100))
