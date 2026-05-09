from django.conf import settings
from django.urls import set_script_prefix
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
            set_script_prefix(config.url_base)
            
        response = self.get_response(request)
        return response
