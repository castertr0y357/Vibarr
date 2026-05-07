import django.utils.timezone as timezone
from ..models import AppConfig

class TimezoneMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        config = AppConfig.get_solo()
        tzname = config.timezone or 'UTC'
        try:
            timezone.activate(tzname)
        except Exception:
            timezone.activate('UTC')
        
        return self.get_response(request)
