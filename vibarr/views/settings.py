from django.db import models
from django.views.generic import TemplateView, View
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib import messages
from django.template.loader import render_to_string

from .mixins import ConfigMixin
from ..models import AppConfig, MediaServerType, APIKey, Persona
from ..forms import AppConfigForm
from ..services.managers.sonarr_service import SonarrService
from ..services.managers.radarr_service import RadarrService
from ..services.managers.seerr_service import SeerrService
from ..services.media.plex_service import PlexService
from ..services.media.plex_auth_service import PlexAuthService
from ..services.media.jellyfin_service import JellyfinService
from ..services.discovery.tmdb_service import TMDBService
from ..services.discovery.tvdb_service import TVDBService
from django_q.tasks import async_task
from ..tasks.discovery.recommendations import refresh_metadata_backlog, revaluate_all_recommendations, refresh_discovery_tracks
from django.contrib.auth.hashers import make_password

import logging

logger = logging.getLogger(__name__)

class GetLibrariesView(View):
    def post(self, request):
        config = AppConfig.get_solo()
        
        # Prefer POST, then GET (for load), then database
        plex_url = request.POST.get('plex_url') or request.GET.get('plex_url') or config.plex_url
        plex_token = request.POST.get('plex_token') or request.GET.get('plex_token') or config.plex_token
        jellyfin_url = request.POST.get('jellyfin_url') or request.GET.get('jellyfin_url') or config.jellyfin_url
        jellyfin_key = request.POST.get('jellyfin_api_key') or request.GET.get('jellyfin_api_key') or config.jellyfin_api_key
        
        providers = []
        if config.media_server_type in [MediaServerType.PLEX, MediaServerType.BOTH]:
            providers.append(PlexService(url=plex_url, token=plex_token))
        if config.media_server_type in [MediaServerType.JELLYFIN, MediaServerType.BOTH]:
            providers.append(JellyfinService(url=jellyfin_url, api_key=jellyfin_key))
            
        libraries_by_server = {}
        for p in providers:
            try:
                server_name = "Plex" if "Plex" in p.__class__.__name__ else "Jellyfin"
                libs = p.get_available_libraries()
                if libs:
                    if server_name not in libraries_by_server:
                        libraries_by_server[server_name] = []
                    libraries_by_server[server_name].extend(libs)
            except Exception as e:
                logger.error(f"Error fetching libraries from provider: {e}")
        
        for server in libraries_by_server:
            libraries_by_server[server] = sorted(list(set(libraries_by_server[server])))

        monitored = [i.strip() for i in config.monitored_libraries.split(',')] if config and config.monitored_libraries else []
        
        return render(request, 'vibarr/partials/library_checklist.html', {
            'libraries_by_server': libraries_by_server,
            'monitored': monitored
        })

    def get(self, request):
        return self.post(request)

class DiscoverPlexServersView(View):
    def get(self, request):
        config = AppConfig.get_solo()
        token = config.plex_token
        if not token:
            return HttpResponse('<div class="text-xs text-rose-500 p-2">Authenticate with Plex first!</div>')
            
        auth = PlexAuthService()
        servers = auth.get_resources(token)
        return render(request, 'vibarr/partials/plex_server_picker.html', {'servers': servers})

class SettingsView(ConfigMixin, TemplateView):
    def get_template_names(self):
        section = self.kwargs.get('section', 'general')
        return [f'vibarr/settings/{section}.html']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        config = AppConfig.get_solo()
        section = self.kwargs.get('section', 'general')
        context['section'] = section
        context['config'] = config
        context['form'] = AppConfigForm(instance=config)
        
        if section == 'automation':
            sonarr = SonarrService()
            radarr = RadarrService()
            try:
                context['sonarr_folders'] = sonarr.get_root_folders()
                context['sonarr_profiles'] = sonarr.get_quality_profiles()
            except Exception:
                context['sonarr_folders'] = []
                context['sonarr_profiles'] = []

            try:
                context['radarr_folders'] = radarr.get_root_folders()
                context['radarr_profiles'] = radarr.get_quality_profiles()
            except Exception:
                context['radarr_folders'] = []
                context['radarr_profiles'] = []
        
        elif section == 'household':
            context['personas'] = Persona.objects.all()
            
        elif section == 'security':
            context['api_keys'] = APIKey.objects.all()
            
        return context

class UpdateSettingsView(View):
    # Fields that belong to each settings section.
    # Only these fields will be updated when saving from that section.
    SECTION_FIELDS = {
        'general': [
            'tmdb_region', 'tmdb_language', 'timezone',
            'max_content_rating',
            'url_base',
            'tautulli_url', 'tautulli_api_key',
            'discord_webhook_url', 'telegram_bot_token', 'telegram_chat_id',
        ],
        'servers': [
            'media_server_type',
            'plex_url', 'plex_token',
            'jellyfin_url', 'jellyfin_api_key',
            'plex_user_filter',
        ],
        'automation': [
            'sonarr_url', 'sonarr_api_key', 'sonarr_root_folder', 'sonarr_quality_profile_id',
            'radarr_url', 'radarr_api_key', 'radarr_root_folder', 'radarr_quality_profile_id',
            'use_seerr', 'seerr_url', 'seerr_api_key',
            'auto_collection_sync',
        ],
        'intelligence': [
            'tmdb_api_key', 'tvdb_api_key', 'tvdb_pin',
            'use_ai_recommendations', 'auto_universe_discovery',
            'auto_tasting_threshold',
            'ai_api_url', 'ai_model', 'ai_api_key',
            'h_rating_weight', 'h_popularity_weight', 'h_genre_weight',
            'h_keyword_weight', 'h_seerr_weight', 'h_collection_weight',
            'movie_influence_on_shows', 'show_influence_on_movies',
            'ignored_genres',
        ],
        'governance': [
            'default_tasting_count', 'tasting_percentage',
            'max_discovered_movies', 'max_discovered_shows',
            'max_tasting_items', 'auto_purge_inactive',
            'universe_page_enabled',
        ],
        'household': [],  # Handled separately via Persona model
        'security': [
            'auth_mode',
        ],
    }

    def post(self, request, *args, **kwargs):
        config = AppConfig.get_solo()
        section = request.POST.get('section', 'general')
        
        # Get the list of fields that this section is allowed to update
        allowed_fields = self.SECTION_FIELDS.get(section, [])
        
        errors = {}
        for field_name in allowed_fields:
            if field_name not in request.POST:
                # Handle checkboxes: unchecked checkboxes are absent from POST
                model_field = AppConfig._meta.get_field(field_name)
                if isinstance(model_field, models.BooleanField):
                    setattr(config, field_name, False)
                continue
            
            value = request.POST.get(field_name)
            model_field = AppConfig._meta.get_field(field_name)
            
            try:
                # Type coercion for specific field types
                if isinstance(model_field, models.BooleanField):
                    setattr(config, field_name, value in ['on', 'true', 'True', '1'])
                elif isinstance(model_field, models.IntegerField):
                    setattr(config, field_name, int(value) if value else None)
                elif isinstance(model_field, models.FloatField):
                    setattr(config, field_name, float(value) if value else None)
                else:
                    setattr(config, field_name, value if value else '')
            except (ValueError, TypeError) as e:
                errors[field_name] = str(e)
        
        if not errors:
            # Manual password hashing
            new_password = request.POST.get('auth_password')
            if new_password and new_password.strip():
                config.auth_password = make_password(new_password)
            
            # Once we save from the settings page, we consider setup "finished"
            config.setup_complete = True
            config.save()
            
            # Handle monitored libraries (special multi-select field)
            if 'libraries_loaded' in request.POST:
                monitored_list = request.POST.getlist('monitored_libs')
                config.monitored_libraries = ",".join(monitored_list)
                config.save()
                
            messages.success(request, "Settings updated successfully.")
        else:
            logger.error(f"Settings update failed. Errors: {errors}")
            messages.error(request, f"Error saving settings: {errors}")
            
        if request.headers.get('HX-Request'):
            response = HttpResponse("")
            if not errors:
                response['HX-Trigger'] = '{"show-toast": {"message": "Settings updated successfully", "type": "success"}}'
            else:
                response['HX-Trigger'] = '{"show-toast": {"message": "Error saving settings. Please check the fields.", "type": "error"}}'
            return response

        url_name = f'settings_{section}'
        try:
            return redirect(url_name)
        except Exception:
            return redirect('settings_general')

class TestSettingsView(View):
    def post(self, request):
        service_type = request.POST.get('type')
        url = request.POST.get('url') or request.POST.get(f'{service_type}_url')
        key = request.POST.get('key') or request.POST.get(f'{service_type}_api_key') or request.POST.get('ai_api_key') or request.POST.get('seerr_api_key')
        token = request.POST.get('token') or request.POST.get('plex_token') or key
        
        error_msg = None
        try:
            success = False
            if service_type == 'plex':
                success = PlexService(url=url, token=token).test_connection()
            elif service_type == 'jellyfin':
                success = JellyfinService(url=url, api_key=key).test_connection()
            elif service_type == 'sonarr':
                SonarrService(url=url, api_key=key).get_root_folders()
                success = True
            elif service_type == 'radarr':
                RadarrService(url=url, api_key=key).get_root_folders()
                success = True
            elif service_type == 'seerr':
                success = SeerrService(url=url, api_key=key).test_connection()
            elif service_type == 'tmdb':
                success = TMDBService(api_key=key).test_connection()
            elif service_type == 'tvdb':
                pin = request.POST.get('pin')
                success = TVDBService(api_key=key, pin=pin).test_connection()
            elif service_type == 'ai':
                success = True
            else:
                return HttpResponse('<span class="text-rose-500 font-bold text-[10px]">Unknown Type</span>')

        except Exception as e:
            success = False
            error_msg = str(e) # Capture full error for toast
            # But keep truncated for the inline display
            display_error = f"Error: {str(e)[:20]}"

        response = render(request, 'vibarr/partials/test_result.html', {
            'success': success,
            'error': error_msg if not success else None
        })
        
        if success:
            response['HX-Trigger'] = '{"show-toast": {"message": "Connection Successful!", "type": "success"}}'
        else:
            # Escape single quotes for JSON
            clean_error = error_msg.replace("'", "\\'")
            response['HX-Trigger'] = f'{{"show-toast": {{"message": "Connection Failed: {clean_error}", "type": "error"}}}}'
            
        return response

class RefreshMetadataView(View):
    def post(self, request):
        
        is_full = request.POST.get('full') == 'true' or request.GET.get('full') == 'true'
        
        if is_full:
            async_task('vibarr.tasks.discovery.recommendations.refresh_metadata_backlog', full_sweep=True)
            response = HttpResponse('<span class="text-amber-500 font-bold text-[10px]">Deep Refresh Started in Background</span>')
            response['HX-Trigger'] = '{"show-toast": {"message": "Deep Metadata Refresh started in background", "type": "success"}}'
            return response
        
        count = refresh_metadata_backlog(full_sweep=False)
        response = HttpResponse(f'<span class="text-green-500 font-bold text-[10px]">Refreshed {count} items</span>')
        response['HX-Trigger'] = f'{{"show-toast": {{"message": "Successfully refreshed {count} items", "type": "success"}}}}'
        return response

class RevaluateRecommendationsView(View):
    def post(self, request):
        mode = request.POST.get('mode', 'scores')
        
        if mode == 'discovery':
            async_task('vibarr.tasks.discovery.recommendations.refresh_discovery_tracks')
            response = HttpResponse('<span class="text-blue-500 font-bold text-[10px]">Fresh Discovery Scout Triggered</span>')
            response['HX-Trigger'] = '{"show-toast": {"message": "Discovery Scout triggered", "type": "success"}}'
            return response
        
        # Default: Re-evaluate scores
        async_task('vibarr.tasks.discovery.recommendations.revaluate_all_recommendations')
        response = HttpResponse('<span class="text-rose-500 font-bold text-[10px]">Score Re-evaluation Started</span>')
        response['HX-Trigger'] = '{"show-toast": {"message": "AI Re-evaluation started", "type": "success"}}'
        return response