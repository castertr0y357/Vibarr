from django.contrib import admin
from ..models import MediaWatchEvent

@admin.register(MediaWatchEvent)
class MediaWatchEventAdmin(admin.ModelAdmin):
    list_display = ('show_title', 'source_server', 'season', 'episode', 'watched_at')
    list_filter = ('source_server', 'watched_at')
    search_fields = ('show_title',)
