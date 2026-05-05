from django.views.generic import View
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import json
import logging
from django_q.tasks import async_task
from ..tasks import poll_media_servers

logger = logging.getLogger(__name__)

@method_decorator(csrf_exempt, name='dispatch')
class PlexWebhookView(View):
    """
    Handles incoming webhooks from Plex.
    Requires 'Webhooks' to be enabled in Plex Media Server settings.
    """
    def post(self, request, *args, **kwargs):
        try:
            # Plex sends webhooks as multipart/form-data with a 'payload' field
            payload_str = request.POST.get('payload')
            if not payload_str:
                return HttpResponse("No payload", status=400)
            
            data = json.loads(payload_str)
            event = data.get('event')
            
            logger.info(f"Plex Webhook received: {event}")
            
            # We only care about media.scrobble (finished watching) 
            # or media.rate (rated something)
            if event in ['media.scrobble', 'media.rate']:
                # Trigger an immediate poll of recent history to process this event
                # This makes Vibarr feel instant instead of waiting for the schedule
                async_task(poll_media_servers)
                
            return JsonResponse({"status": "received"})
        except Exception as e:
            logger.error(f"Plex Webhook Error: {e}")
            return HttpResponse(status=500)

@method_decorator(csrf_exempt, name='dispatch')
class JellyfinWebhookView(View):
    """
    Handles incoming webhooks from Jellyfin (Generic Destination).
    """
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            event = data.get('NotificationType')
            
            logger.info(f"Jellyfin Webhook received: {event}")
            
            if event == 'PlaybackStopped':
                async_task(poll_media_servers)
                
            return JsonResponse({"status": "received"})
        except Exception as e:
            logger.error(f"Jellyfin Webhook Error: {e}")
            return HttpResponse(status=500)
