from django.conf import settings
from ..models import AppConfig

class URLBaseMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        config = AppConfig.get_solo()
        if config.url_base:
            # Set the script name for this request
            # This ensures reverse() and {% url %} generate the correct paths
            request.environ['SCRIPT_NAME'] = config.url_base
            # Also tell Django to use this script name globally for this thread
            from django.urls import set_script_prefix
            set_script_prefix(config.url_base)
            
        response = self.get_response(request)
        return response
