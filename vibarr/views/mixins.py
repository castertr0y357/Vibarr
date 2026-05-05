from django.shortcuts import redirect
from django.urls import reverse
from django.http import JsonResponse
from django.utils import timezone
from functools import wraps
from ..models import AppConfig, APIKey

class ConfigMixin:
    """Mixin to provide application configuration to the context."""
    def dispatch(self, request, *args, **kwargs):
        config = AppConfig.get_solo()
        
        # Redirect to setup if not configured and not already on the setup page
        if not config.is_configured and request.resolver_match.url_name != 'setup_wizard':
            return redirect('setup_wizard')
            
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        config = AppConfig.get_solo()
        context['config'] = config
        context['plex_connected'] = bool(config.plex_token)
        return context

class APIMixin:
    """Mixin to handle API authentication and JSON responses."""
    def dispatch(self, request, *args, **kwargs):
        # Check for API Key in headers
        raw_api_key = request.headers.get('X-API-Key')
        request.is_api_request = False
        
        if raw_api_key:
            # We must iterate over all keys since we can't look up by hash directly
            # This is fine for a small number of keys. For large scale, a prefix strategy is needed.
            active_keys = APIKey.objects.filter(is_active=True)
            for key_obj in active_keys:
                if key_obj.verify_key(raw_api_key):
                    # Throttle update to once every 10 minutes
                    now = timezone.now()
                    if not key_obj.last_used_at or (now - key_obj.last_used_at).total_seconds() > 600:
                        key_obj.last_used_at = now
                        key_obj.save(update_fields=['last_used_at'])
                    
                    request.is_api_request = True
                    break
            
            if not request.is_api_request:
                return JsonResponse({'error': 'Invalid API Key'}, status=403)
        elif request.headers.get('Accept') == 'application/json':
            # JSON request without a key
            return JsonResponse({'error': 'API Key required'}, status=401)
            
        return super().dispatch(request, *args, **kwargs)

    def render_to_response(self, context, **response_kwargs):
        if self.request.is_api_request or self.request.headers.get('Accept') == 'application/json':
            # For now, we expect views to implement get_api_data()
            data = self.get_api_data(context) if hasattr(self, 'get_api_data') else context
            return JsonResponse(data, **response_kwargs)
        return super().render_to_response(context, **response_kwargs)
