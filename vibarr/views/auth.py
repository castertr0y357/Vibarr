from django.views.generic import RedirectView, TemplateView
from django.shortcuts import redirect, render
from django.urls import reverse
import urllib.parse
from ..services.media.plex_auth_service import PlexAuthService
from ..models import AppConfig

class StartPlexAuthView(RedirectView):
    def get_redirect_url(self, *args, **kwargs):
        auth = PlexAuthService()
        pin_data = auth.get_pin()
        self.request.session['plex_pin_id'] = pin_data['id']
        
        # Build absolute forward URL for callback
        forward_url = self.request.build_absolute_uri(reverse('finish_plex_auth'))
        encoded_forward = urllib.parse.quote(forward_url)
        
        return f"https://app.plex.tv/auth/#!?clientID={auth.headers['X-Plex-Client-Identifier']}&code={pin_data['code']}&context%5Bdevice%5D%5Bproduct%5D=Vibarr&forwardUrl={encoded_forward}"

class FinishPlexAuthView(TemplateView):
    template_name = 'vibarr/plex_auth_waiting.html'

    def get(self, request, *args, **kwargs):
        pin_id = request.session.get('plex_pin_id')
        if not pin_id:
            return redirect('dashboard')
        
        auth = PlexAuthService()
        token = auth.check_pin(pin_id)
        
        if token:
            config = AppConfig.objects.first()
            config.plex_token = token
            config.save()
            return redirect('dashboard')
        
        return super().get(request, *args, **kwargs)
