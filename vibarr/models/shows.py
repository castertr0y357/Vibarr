from django.db import models
from .enums import ShowState, MediaType
from .config import AppConfig

class Show(models.Model):
    title = models.CharField(max_length=255)
    tmdb_id = models.IntegerField(unique=True)
    media_type = models.CharField(
        max_length=10,
        choices=MediaType.choices,
        default=MediaType.SHOW,
        db_index=True
    )
    sonarr_id = models.IntegerField(null=True, blank=True)
    radarr_id = models.IntegerField(null=True, blank=True)
    poster_path = models.CharField(max_length=500, null=True, blank=True)
    runtime = models.IntegerField(null=True, blank=True, help_text="Average episode runtime in minutes")
    content_rating = models.CharField(max_length=20, null=True, blank=True)
    content_advisory = models.CharField(max_length=500, null=True, blank=True, help_text="Keywords like Violence, Nudity, etc.")
    state = models.CharField(
        max_length=20,
        choices=ShowState.choices,
        default=ShowState.SUGGESTED,
        db_index=True
    )
    is_pinned = models.BooleanField(default=False, db_index=True)
    has_notified_ready = models.BooleanField(default=False)
    tasting_episodes_count = models.IntegerField(default=3, help_text="Number of episodes to download for tasting")
    streaming_providers = models.CharField(max_length=500, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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
            # Note: We should ideally prefetch_related 'mediawatchevent_set' to avoid N+1
            event = self.mediawatchevent_set.last()
            if event and event.duration:
                return min(100, int((event.view_offset / event.duration) * 100))
            return 0
        else:
            # Optimization: count() is better than values().distinct().count() if we don't have many events
            watched = self.mediawatchevent_set.values('season', 'episode').distinct().count()
            return min(100, int((watched / self.tasting_episodes_count) * 100))
