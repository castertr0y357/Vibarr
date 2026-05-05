from django.contrib import admin
from ..models import Persona

@admin.register(Persona)
class PersonaAdmin(admin.ModelAdmin):
    list_display = ('name', 'max_content_rating', 'auto_switch_enabled')
    fields = ('name', 'max_content_rating', 'ignored_genres', 'auto_switch_enabled', 'start_time', 'end_time')
