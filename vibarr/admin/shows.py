from django.contrib import admin
from ..models import Show

@admin.register(Show)
class ShowAdmin(admin.ModelAdmin):
    list_display = ('title', 'media_type', 'state', 'content_rating', 'updated_at')
    list_filter = ('media_type', 'state', 'content_rating')
    search_fields = ('title', 'tmdb_id')
