from django.views.generic import TemplateView, View
from django.shortcuts import render, redirect
from django.contrib import messages
from .mixins import ConfigMixin
from ..models import AppConfig, MediaServerType
from ..forms import AppConfigForm
from ..services.managers.sonarr_service import SonarrService
from ..services.managers.radarr_service import RadarrService
from ..services.media.plex_service import PlexService
from ..services.media.jellyfin_service import JellyfinService
import logging

logger = logging.getLogger(__name__)

class GetLibrariesView(View):
    def get(self, request):
        config = AppConfig.get_solo()
        providers = []
        if config.media_server_type in [MediaServerType.PLEX, MediaServerType.BOTH]:
            providers.append(PlexService())
        if config.media_server_type in [MediaServerType.JELLYFIN, MediaServerType.BOTH]:
            providers.append(JellyfinService())
            
        libraries = []
        for p in providers:
            try:
                libraries.extend(p.get_available_libraries())
            except Exception as e:
                logger.error(f"Error fetching libraries from provider: {e}")
        
        # Unique and sorted
        libraries = sorted(list(set(libraries)))
        ignored = [i.strip() for i in config.ignored_libraries.split(',')] if config and config.ignored_libraries else []
        
        return render(request, 'vibarr/partials/library_checklist.html', {
            'libraries': libraries,
            'ignored': ignored
        })

class SettingsView(ConfigMixin, TemplateView):
    template_name = 'vibarr/settings.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        config = AppConfig.get_solo()
        context['form'] = AppConfigForm(instance=config)
        
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

        from ..models import APIKey
        context['api_keys'] = APIKey.objects.all()
        return context

class UpdateSettingsView(View):
    def post(self, request, *args, **kwargs):
        config = AppConfig.get_solo()
        form = AppConfigForm(request.POST, instance=config)
        
        if form.is_valid():
            form.save()
            # Handle ignored libraries specially if they aren't part of the main form fields
            # (In our case they are joined in the form save, but let's ensure it)
            ignored_list = request.POST.getlist('ignored_libs')
            if ignored_list:
                config.ignored_libraries = ",".join(ignored_list)
                config.save()
                
            messages.success(request, "Settings updated successfully.")
            logger.info("Application settings updated via form.")
        else:
            messages.error(request, f"Error saving settings: {form.errors}")
            logger.error(f"Settings update error: {form.errors}")
            
        return redirect('settings')
