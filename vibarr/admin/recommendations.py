from django.contrib import admin
from ..models import Recommendation

@admin.register(Recommendation)
class RecommendationAdmin(admin.ModelAdmin):
    list_display = ('suggested_show', 'source_title', 'score', 'created_at')
    list_filter = ('score',)
    search_fields = ('suggested_show__title', 'source_title')
