from django.views.generic import TemplateView, View
from django.shortcuts import render, redirect
from django.http import HttpResponse
from ..models import AppConfig
from ..models.enums import MediaServerType
from ..services.managers.sonarr_service import SonarrService
from ..services.managers.radarr_service import RadarrService
from ..services.media.plex_service import PlexService
from ..services.media.jellyfin_service import JellyfinService
from ..services.media.plex_auth_service import PlexAuthService

class SetupWizardView(TemplateView):
    template_name = 'vibarr/setup/wizard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        config = AppConfig.get_solo()
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
        config = AppConfig.get_solo()
        action = request.POST.get('action')
        
        if action == 'save_media':
            # Handle multi-select
            has_plex = 'PLEX' in request.POST.getlist('server_type')
            has_jellyfin = 'JELLYFIN' in request.POST.getlist('server_type')
            
            if has_plex and has_jellyfin:
                config.media_server_type = MediaServerType.BOTH
            elif has_plex:
                config.media_server_type = MediaServerType.PLEX
            elif has_jellyfin:
                config.media_server_type = MediaServerType.JELLYFIN
            
            if 'plex_url' in request.POST:
                config.plex_url = request.POST.get('plex_url')
            if 'plex_token' in request.POST:
                config.plex_token = request.POST.get('plex_token')
                
            config.jellyfin_url = request.POST.get('jellyfin_url')
            config.jellyfin_api_key = request.POST.get('jellyfin_key')
            config.save()
            return render(request, 'vibarr/setup/steps/automation.html', self.get_automation_context(config))
            
        elif action == 'save_automation':
            config.sonarr_url = request.POST.get('sonarr_url')
            config.sonarr_api_key = request.POST.get('sonarr_key')
            config.radarr_url = request.POST.get('radarr_url')
            config.radarr_api_key = request.POST.get('radarr_key')
            config.sonarr_root_folder = request.POST.get('sonarr_root')
            config.radarr_root_folder = request.POST.get('radarr_root')
            config.save()
            return render(request, 'vibarr/setup/steps/intelligence.html', {'config': config})
            
        elif action == 'save_intelligence':
            config.tmdb_api_key = request.POST.get('tmdb_api_key')
            config.use_ai_recommendations = request.POST.get('use_ai') == 'on'
            config.ai_api_url = request.POST.get('ai_url')
            config.ai_model = request.POST.get('ai_model')
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

class PlexPinRequestView(View):
    def get(self, request):
        auth = PlexAuthService()
        pin_data = auth.get_pin() # {'id': ..., 'code': ...}
        return render(request, 'vibarr/setup/partials/plex_pin.html', {
            'pin_id': pin_data['id'],
            'pin_code': pin_data['code']
        })

class PlexPinPollView(View):
    def get(self, request, pin_id):
        auth = PlexAuthService()
        token = auth.check_pin(pin_id)
        if token:
            config = AppConfig.get_solo()
            config.plex_token = token
            config.save()
            return HttpResponse(f"""
                <div class="flex items-center justify-center gap-2 text-green-500 font-bold py-2 bg-green-500/10 rounded-xl border border-green-500/20 animate-fade-in">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
                    Authenticated!
                </div>
            """)
        
        # Still waiting - explicitly target the status div to avoid over-swapping
        return HttpResponse(f"""
            <div id="pin-poll-target"
                 hx-get="/setup/plex/poll/{pin_id}/" 
                 hx-trigger="load delay:3s" 
                 hx-target="#pin-poll-target"
                 hx-swap="outerHTML" 
                 class="text-[10px] text-gray-500 flex items-center justify-center gap-2 pt-2 border-t border-white/5">
                <div class="w-1.5 h-1.5 bg-rose-500 rounded-full animate-pulse"></div>
                Waiting for Plex authorization...
            </div>
        """)

class ResetSetupView(View):
    def post(self, request):
        config = AppConfig.get_solo()
        # Optional: reset fields? Or just redirect.
        # config.plex_token = None ...
        # config.save()
        return redirect('setup_wizard')

class TestAutomationView(View):
    def post(self, request):
        service_type = request.POST.get('type')
        # Check for both generic and service-specific names
        url = request.POST.get('url') or request.POST.get(f'{service_type}_url')
        api_key = request.POST.get('api_key') or request.POST.get(f'{service_type}_key')
        
        if not url or not api_key:
            return HttpResponse(f'<span class="text-rose-500 font-bold text-xs">Missing URL or Key (Found: {url}, {api_key})</span>')

        try:
            folders = []
            if service_type == 'sonarr':
                service = SonarrService(url=url, api_key=api_key)
                folders = service.get_root_folders()
            elif service_type == 'radarr':
                service = RadarrService(url=url, api_key=api_key)
                folders = service.get_root_folders()
            else:
                return HttpResponse('<span class="text-rose-500 font-bold text-xs">Invalid type</span>')
                
            # Create the success message
            response_html = '<span class="text-green-500 font-bold text-xs flex items-center gap-1"><svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg> Connection Successful</span>'
            
            # Prepare OOB swap for the dropdown
            folder_options = "".join([f'<option value="{f["path"]}">{f["path"]}</option>' for f in folders])
            if not folder_options:
                folder_options = '<option disabled>No folders found.</option>'
            
            select_id = f"{service_type}_root_select"
            response_html += f'<select id="{select_id}" name="{service_type}_root" hx-swap-oob="innerHTML" class="w-full bg-black/40 border border-white/10 rounded-xl p-4 text-white text-sm focus:outline-none focus:border-rose-500 transition">{folder_options}</select>'
            
            return HttpResponse(response_html)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Wizard Automation Test Error: {e}")
            return HttpResponse(f'<span class="text-rose-500 font-bold text-xs">Connection Failed: {str(e)[:40]}...</span>')
