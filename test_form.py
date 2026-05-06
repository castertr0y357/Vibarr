import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vibarr_project.settings')
django.setup()

from vibarr.models import AppConfig
from vibarr.forms import AppConfigForm

config = AppConfig.get_solo()
config.media_server_type = "PLEX"
config.save()

data = {
    'media_server_type': 'PLEX',
    'tmdb_region': 'US',
    'tmdb_language': 'en-US',
    'max_content_rating': 'TV-14',
    'default_tasting_count': '3',
    'auto_tasting_threshold': '9.5',
    'ai_model': 'llama3',
    'ai_api_url': 'http://localhost:11434',
    # Intentionally missing other fields to see what happens
}
form = AppConfigForm(data, instance=config)
print("Is valid?", form.is_valid())
if not form.is_valid():
    print("Errors:", form.errors)
