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

import logging

logger = logging.getLogger(__name__)

class GetLibrariesView(View):
    def post(self, request):
        plex_url = request.POST.get('plex_url')
        plex_token = request.POST.get('plex_token')
        jellyfin_url = request.POST.get('jellyfin_url')
        jellyfin_key = request.POST.get('jellyfin_api_key')
        
        config = AppConfig.get_solo()
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
    def post(self, request, *args, **kwargs):
        config = AppConfig.get_solo()
        form = AppConfigForm(request.POST, instance=config)
        
        if form.is_valid():
            form.save()
            if 'libraries_loaded' in request.POST:
                monitored_list = request.POST.getlist('monitored_libs')
                config.monitored_libraries = ",".join(monitored_list)
                config.save()
            messages.success(request, "Settings updated successfully.")
        else:
            messages.error(request, f"Error saving settings: {form.errors}")
            
        section = request.POST.get('section', 'general')
        
        if request.headers.get('HX-Request'):
            response = HttpResponse("")
            if form.is_valid():
                response['HX-Trigger'] = '{"show-toast": "Settings updated successfully"}'
            else:
                response['HX-Trigger'] = f'{{"show-toast": "Error saving settings: {form.errors}"}}'
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
            error_msg = f"Error: {str(e)[:20]}"

        return render(request, 'vibarr/partials/test_result.html', {
            'success': success,
            'error': error_msg
        })

class RefreshMetadataView(View):
    def post(self, request):
        
        is_full = request.POST.get('full') == 'true' or request.GET.get('full') == 'true'
        
        if is_full:
            async_task('vibarr.tasks.discovery.recommendations.refresh_metadata_backlog', full_sweep=True)
            return HttpResponse('<span class="text-amber-500 font-bold text-[10px]">Deep Refresh Started in Background</span>')
        
        count = refresh_metadata_backlog(full_sweep=False)
        return HttpResponse(f'<span class="text-green-500 font-bold text-[10px]">Refreshed {count} items</span>')

class RevaluateRecommendationsView(View):
    def post(self, request):
        mode = request.POST.get('mode', 'scores')
        
        if mode == 'discovery':
            async_task('vibarr.tasks.discovery.recommendations.refresh_discovery_tracks')
            return HttpResponse('<span class="text-blue-500 font-bold text-[10px]">Fresh Discovery Scout Triggered</span>')
        
        # Default: Re-evaluate scores
        async_task('vibarr.tasks.discovery.recommendations.revaluate_all_recommendations')
        return HttpResponse('<span class="text-rose-500 font-bold text-[10px]">Score Re-evaluation Started</span>')