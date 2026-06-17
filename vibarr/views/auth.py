from django.views.generic import RedirectView, TemplateView
from django.shortcuts import redirect, render
from django.urls import reverse
import urllib.parse
from ..services.media.plex_auth_service import PlexAuthService
from ..models import AppConfig
from django.contrib.auth.hashers import check_password
from django.views import View

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

class LoginView(View):
    def get(self, request):
        if request.session.get('vibarr_auth'):
            return redirect('dashboard')
        return render(request, 'vibarr/login.html')

    def post(self, request):
        from django.core.cache import cache
        
        # Get IP address for rate limiting
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
            
        cache_key = f"login_attempts_{ip}"
        attempts = cache.get(cache_key, 0)
        
        if attempts >= 5:
            return render(request, 'vibarr/login.html', {
                'error': 'Too many failed login attempts. Please try again in 5 minutes.'
            })

        password = request.POST.get('password')
        config = AppConfig.get_solo()
        
        if not config.auth_password:
            return render(request, 'vibarr/login.html', {
                'error': 'Authentication is enabled but no access code has been set. Use the Django admin or CLI to set a password.'
            })

        if check_password(password, config.auth_password):
            # Clear rate limit state on successful login
            cache.delete(cache_key)
            # Cycle session key to prevent Session Fixation
            request.session.cycle_key()
            request.session['vibarr_auth'] = True
            request.session.set_expiry(0) # Browser close or standard session timeout
            return redirect('dashboard')
        else:
            cache.set(cache_key, attempts + 1, 300)
            return render(request, 'vibarr/login.html', {'error': 'Invalid password'})

class LogoutView(View):
    def post(self, request):
        if 'vibarr_auth' in request.session:
            del request.session['vibarr_auth']
        return redirect('login')
