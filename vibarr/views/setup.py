from django.views.generic import TemplateView, View
from django.shortcuts import render, redirect
from ..models import AppConfig
from ..services.managers.sonarr_service import SonarrService
from ..services.managers.radarr_service import RadarrService
from ..services.media.plex_service import PlexService
from ..services.media.jellyfin_service import JellyfinService

class SetupWizardView(TemplateView):
    template_name = 'vibarr/setup/wizard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        config = AppConfig.objects.first()
        if not config:
            config = AppConfig.objects.create()
        context['config'] = config
        
        # Determine current step
        step = self.request.GET.get('step', 'welcome')
        context['step'] = step
        
        # Load data for specific steps
        if step == 'automation':
            try:
                context['sonarr_folders'] = SonarrService().get_root_folders()
                context['radarr_folders'] = RadarrService().get_root_folders()
            except Exception:
                context['sonarr_folders'] = []
                context['radarr_folders'] = []
                
        return context

    def get(self, request, *args, **kwargs):
        if request.headers.get('HX-Request'):
            # Return only the inner content for HTMX transitions
            context = self.get_context_data(**kwargs)
            step = context['step']
            return render(request, f'vibarr/setup/steps/{step}.html', context)
        return super().get(request, *args, **kwargs)

class SetupActionView(View):
    def post(self, request):
        config = AppConfig.objects.first()
        action = request.POST.get('action')
        
        if action == 'save_media':
            config.media_server_type = request.POST.get('server_type')
            config.plex_url = request.POST.get('plex_url')
            config.jellyfin_url = request.POST.get('jellyfin_url')
            config.jellyfin_api_key = request.POST.get('jellyfin_key')
            config.save()
            return render(request, 'vibarr/setup/steps/automation.html', self.get_automation_context(config))
            
        elif action == 'save_automation':
            config.sonarr_root_folder = request.POST.get('sonarr_root')
            config.radarr_root_folder = request.POST.get('radarr_root')
            config.save()
            return render(request, 'vibarr/setup/steps/intelligence.html', {'config': config})
            
        elif action == 'save_intelligence':
            config.use_ai_recommendations = request.POST.get('use_ai') == 'on'
            config.ai_api_url = request.POST.get('ai_url')
            config.save()
            return render(request, 'vibarr/setup/steps/finish.html', {'config': config})
            
        return redirect('dashboard')

    def get_automation_context(self, config):
        context = {'config': config}
        try:
            context['sonarr_folders'] = SonarrService().get_root_folders()
            context['radarr_folders'] = RadarrService().get_root_folders()
        except Exception:
            context['sonarr_folders'] = []
            context['radarr_folders'] = []
        return context
