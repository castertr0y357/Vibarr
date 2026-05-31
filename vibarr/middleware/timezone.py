import logging
from typing import Callable
from django.http import HttpRequest, HttpResponse
import django.utils.timezone as timezone
from ..models import AppConfig

logger = logging.getLogger(__name__)

class TimezoneMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        config = AppConfig.get_solo()
        tzname: str = config.timezone or 'UTC'
        try:
            timezone.activate(tzname)
        except Exception as e:
            logger.warning(f"Timezone - Warning - Failed to activate timezone '{tzname}': {e}")
            timezone.activate('UTC')
        
        return self.get_response(request)
