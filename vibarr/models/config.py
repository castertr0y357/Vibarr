from django.db import models
from django.core.cache import cache
from .enums import MediaServerType

class Persona(models.Model):
    name = models.CharField(max_length=50)
    max_content_rating = models.CharField(max_length=10, default="NR", help_text="Max content rating allowed (e.g. PG, TV-14)")
    ignored_genres = models.TextField(default="", blank=True, help_text="Comma-separated list of genres to ignore")
    
    # Automation
    auto_switch_enabled = models.BooleanField(default=False)
    start_time = models.TimeField(null=True, blank=True, help_text="When to auto-activate this lens.")
    end_time = models.TimeField(null=True, blank=True, help_text="When to deactivate.")

    def __str__(self):
        return self.name

class AppConfig(models.Model):
    # Media Server Choice
    media_server_type = models.CharField(
        max_length=10, 
        choices=MediaServerType.choices, 
        default=MediaServerType.PLEX
    )
    active_persona = models.ForeignKey(Persona, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Plex Settings
    plex_token = models.TextField(null=True, blank=True)
    plex_url = models.TextField(null=True, blank=True)
    
    # Jellyfin Settings
    jellyfin_url = models.TextField(null=True, blank=True)
    jellyfin_api_key = models.TextField(null=True, blank=True)
    
    # Manager Settings
    sonarr_url = models.TextField(null=True, blank=True)
    sonarr_api_key = models.TextField(null=True, blank=True)
    sonarr_root_folder = models.TextField(null=True, blank=True)
    sonarr_quality_profile_id = models.IntegerField(null=True, blank=True)
    
    radarr_url = models.TextField(null=True, blank=True)
    radarr_api_key = models.TextField(null=True, blank=True)
    radarr_root_folder = models.TextField(null=True, blank=True)
    radarr_quality_profile_id = models.IntegerField(null=True, blank=True)
    
    # External APIs
    tmdb_api_key = models.TextField(null=True, blank=True)
    tvdb_api_key = models.TextField(null=True, blank=True)
    tvdb_pin = models.TextField(null=True, blank=True)
    tautulli_url = models.TextField(null=True, blank=True)
    tautulli_api_key = models.TextField(null=True, blank=True)

    # Companion Apps (Optional)
    use_seerr = models.BooleanField(default=False, help_text="Sync recommendations as requests to Overseerr/Jellyseerr")
    seerr_url = models.TextField(null=True, blank=True, help_text="Seerr/Overseerr/Jellyseerr URL")
    seerr_api_key = models.TextField(null=True, blank=True)
    
    # Notifications
    discord_webhook_url = models.TextField(null=True, blank=True)
    telegram_bot_token = models.TextField(null=True, blank=True)
    telegram_chat_id = models.TextField(null=True, blank=True)
    
    # AI Settings
    use_ai_recommendations = models.BooleanField(default=True)
    auto_universe_discovery = models.BooleanField(default=False)
    auto_tasting_threshold = models.FloatField(default=9.5, help_text="AI confidence score (0-10) above which a recommendation is automatically sent to 'Tasting'.")
    
    ai_api_url = models.URLField(default="http://localhost:11434/v1/chat/completions")
    ai_model = models.CharField(max_length=100, default="gemma3:4b")
    ai_api_key = models.CharField(max_length=255, null=True, blank=True, help_text="Optional API Key for remote instances")
    
    # Content Filtering
    tmdb_region = models.CharField(max_length=2, default="US", help_text="ISO-3166-1 region code for ratings and availability")
    tmdb_language = models.CharField(max_length=5, default="en-US", help_text="ISO-639-1 language code")
    timezone = models.CharField(max_length=50, default="UTC", help_text="Application timezone for logs and display")
    max_content_rating = models.CharField(max_length=10, default="TV-14", help_text="Maximum rating to show without warning")
    ignored_genres = models.TextField(default="", blank=True, help_text="Comma-separated list of genres to ignore (e.g. 'Horror, Reality TV')")
    monitored_libraries = models.TextField(default="", blank=True, help_text="Comma-separated list of library names to monitor")
    url_base = models.CharField(max_length=100, default="", blank=True, help_text="Base URL path for reverse proxies (e.g. '/vibarr').")
    plex_user_filter = models.CharField(max_length=100, null=True, blank=True, help_text="Only learn from this User ID")
    
    # Defaults
    default_tasting_count = models.IntegerField(default=3, help_text="Default number of episodes for a new show tasting")
    # Governance & Growth
    max_discovered_movies = models.IntegerField(default=50, help_text="Maximum movies to keep in the Discovery Feed.")
    max_discovered_shows = models.IntegerField(default=50, help_text="Maximum shows to keep in the Discovery Feed.")
    max_tasting_items = models.IntegerField(default=50, help_text="Maximum total number of active tastings allowed at once.")
    auto_purge_inactive = models.BooleanField(default=False, help_text="Automatically remove tastings with no progress after 14 days.")
    
    # Intelligence Influence
    movie_influence_on_shows = models.IntegerField(default=20, help_text="How much movie taste influences show discovery (0-100).")
    show_influence_on_movies = models.IntegerField(default=20, help_text="How much show taste influences movie discovery (0-100).")
    
    # Heuristic Preferences
    h_rating_weight = models.IntegerField(default=50, help_text="Weight for TMDB/IMDB ratings (0-100)")
    h_popularity_weight = models.IntegerField(default=30, help_text="Weight for TMDB popularity (0-100)")
    h_genre_weight = models.IntegerField(default=100, help_text="Weight for genre matching (0-100)")
    h_keyword_weight = models.IntegerField(default=70, help_text="Weight for keyword matching (0-100)")
    h_seerr_weight = models.IntegerField(default=40, help_text="Weight for Seerr request history (0-100)")
    h_collection_weight = models.IntegerField(default=60, help_text="Weight for collection matching (0-100)")
    
    last_sync = models.DateTimeField(null=True, blank=True)
    is_syncing = models.BooleanField(default=False)
    sync_status = models.TextField(default="", blank=True)
    
    # Universe Architect
    auto_collection_sync = models.BooleanField(default=False, help_text="Automatically create collections in Plex/Jellyfin for detected universes.")
    universe_page_enabled = models.BooleanField(default=True)

    @property
    def is_configured(self):
        """Checks if the minimum required settings are present."""
        has_media_server = bool(self.plex_token or self.jellyfin_api_key)
        has_manager = bool(self.sonarr_url or self.radarr_url)
        return has_media_server and has_manager

    def save(self, *args, **kwargs):
        # Enforce singleton
        if not self.pk and AppConfig.objects.exists():
            return # Don't allow multiple configs
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass # Don't allow deletion of config

    @classmethod
    def get_solo(cls):
        """Retrieves the singleton config."""
        config = cls.objects.first()
        if not config:
            config = cls.objects.create()
        return config

    def __str__(self):
        return "Application Configuration"
    
    class Meta:
        verbose_name_plural = "Application Configuration"

