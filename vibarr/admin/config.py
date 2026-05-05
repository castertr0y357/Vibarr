from django.contrib import admin
from ..models import AppConfig

@admin.register(AppConfig)
class AppConfigAdmin(admin.ModelAdmin):
    list_display = ('media_server_type', 'plex_url', 'jellyfin_url', 'ai_model', 'last_sync')
    fieldsets = (
        ('Media Servers', {'fields': ('media_server_type', 'plex_url', 'plex_token', 'jellyfin_url', 'jellyfin_api_key')}),
        ('Automation Managers', {'fields': ('sonarr_root_folder', 'sonarr_quality_profile_id', 'radarr_root_folder', 'radarr_quality_profile_id')}),
        ('Companion Apps', {'fields': ('seerr_url', 'seerr_api_key', 'bazarr_url', 'prowlarr_url')}),
        ('AI Engine', {'fields': ('ai_api_url', 'ai_model', 'ai_api_key')}),
        ('Filtering', {'fields': ('max_content_rating', 'ignored_genres', 'plex_user_filter')}),
    )
