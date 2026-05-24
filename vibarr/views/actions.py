from django.views.generic import View, RedirectView
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.template.loader import render_to_string
from django.urls import reverse
from django.db import transaction

from django_q.tasks import async_task

from ..models import Show, ShowState, AppConfig, MediaServerType, MediaWatchEvent
from ..services.managers.sonarr_service import SonarrService
from ..services.managers.radarr_service import RadarrService
from ..services.media.plex_service import PlexService
from ..services.media.jellyfin_service import JellyfinService
from ..services.discovery.ai_service import AIService
from ..tasks import (
    start_tasting, 
    poll_media_servers, 
    sync_external_states, 
    batch_universe_sync
)
from .mixins import ConfigMixin, APIMixin

import logging
import json
from ..tasks.discovery.recommendations import reevaluate_single_show

logger = logging.getLogger(__name__)


# Return an empty string, allowing hx-swap="delete" to remove the element without DOM clutter
HTMX_REMOVE = ""

class RejectShowView(View):
    def post(self, request, show_id):
        show = get_object_or_404(Show, id=show_id)
        show.state = ShowState.REJECTED
        show.save()
        if request.headers.get('HX-Request'):
            response = HttpResponse(HTMX_REMOVE)
            response['HX-Trigger'] = 'discovery-changed'
            return response
        if getattr(request, 'is_api_request', False):
            return JsonResponse({'status': 'success', 'message': f'Show {show_id} rejected'})
        return redirect('dashboard')

class TogglePinShowView(View):
    def post(self, request, show_id):
        show = get_object_or_404(Show, id=show_id)
        show.is_pinned = not show.is_pinned
        show.save()
        if request.headers.get('HX-Request'):
            return render(request, 'vibarr/partials/pin_button.html', {'show': show})
        return redirect('dashboard')

class StopAndDeleteShowView(View):
    def post(self, request, show_id):
        show = get_object_or_404(Show, id=show_id)
        
        # Hardening: Only progress if deletion is successful or not applicable
        try:
            if show.sonarr_id:
                SonarrService().delete_series(show.sonarr_id)
            if show.radarr_id:
                RadarrService().delete_movie(show.radarr_id)
        except Exception as e:
            logger.error(f"External service delete error: {e}")
            messages.error(request, f"Failed to remove '{show.title}' from manager. Is the service online?")
            return redirect('dashboard')
        
        show.state = ShowState.REJECTED
        show.save()
        
        messages.success(request, f"Removed '{show.title}' from tastings.")
        if request.headers.get('HX-Request'):
            response = HttpResponse(HTMX_REMOVE)
            response['HX-Trigger'] = 'tasting-changed'
            return response
        return redirect('dashboard')

class MarkWatchedView(View):
    def post(self, request, show_id):
        show = get_object_or_404(Show, id=show_id)
        
        # Hardening: Use transaction to ensure both operations succeed
        with transaction.atomic():
            show.state = ShowState.WATCHED
            show.save()
            
            # Inform history to avoid re-suggesting
            MediaWatchEvent.objects.get_or_create(
                event_id=f"MANUAL_{show.tmdb_id}",
                defaults={
                    'source_server': 'MANUAL',
                    'show_title': show.title,
                    'tmdb_id': show.tmdb_id,
                    'media_type': show.media_type,
                    'watched_at': timezone.now(),
                    'season': 0,
                    'episode': 0,
                }
            )
        
        if request.headers.get('HX-Request'):
            response = HttpResponse(HTMX_REMOVE)
            response['HX-Trigger'] = 'discovery-changed'
            return response
        return redirect('dashboard')

class TasteShowView(View):
    def post(self, request, show_id):
        show = get_object_or_404(Show, id=show_id)
        show.state = ShowState.TASTING
        show.save()
        
        async_task(start_tasting, show.id)
        
        if request.headers.get('HX-Request'):
            tasting_shows = Show.objects.filter(state=ShowState.TASTING).order_by('-updated_at')
            html = render_to_string('vibarr/partials/active_tastings.html', {'tasting': tasting_shows}, request=request)
            dashboard_url = reverse('dashboard') + '?partial=tasting'
            oob = f'<div id="active-tastings-container" hx-swap-oob="true" hx-get="{dashboard_url}" hx-trigger="sync-complete from:body, tasting-changed from:body" hx-sync="this:replace" hx-indicator="#tasting-indicator" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-8">{html}</div>'
            response = HttpResponse(oob)
            response['HX-Trigger'] = 'discovery-changed'
            return response
            
        messages.info(request, f"Started tasting for '{show.title}'.")
        return redirect('dashboard')

class ManualSyncView(APIMixin, View):
    def get(self, request, *args, **kwargs):
        config = AppConfig.get_solo()
        config.is_syncing = True
        config.sync_status = "Sync task queued..."
        config.save()
        
        async_task(poll_media_servers, hours=72)
        async_task(sync_external_states)
        
        if request.headers.get('HX-Request'):
            response = HttpResponse("")
            response['HX-Trigger'] = '{"show-toast": "Manual sync triggered."}'
            return response

        messages.success(request, "Manual sync triggered.")
        if getattr(request, 'is_api_request', False):
            return JsonResponse({'status': 'success', 'message': 'Manual sync triggered'})
        return redirect('dashboard')

class UniverseSyncView(APIMixin, View):
    def get(self, request, *args, **kwargs):
        async_task(batch_universe_sync)
        
        if request.headers.get('HX-Request'):
            response = HttpResponse("")
            response['HX-Trigger'] = '{"show-toast": "Universe Architect: Batch sync triggered."}'
            return response

        messages.success(request, "Universe Architect: Batch sync triggered for all committed items.")
        if getattr(request, 'is_api_request', False):
            return JsonResponse({'status': 'success', 'message': 'Batch universe sync triggered'})
        return redirect('dashboard')

class HealthCheckView(View):
    def get(self, request, service_type):
        mini = request.GET.get('mini') == 'true'
        try:
            if service_type == 'sonarr':
                SonarrService().get_root_folders()
                success = True
            elif service_type == 'radarr':
                RadarrService().get_root_folders()
                success = True
            elif service_type == 'jellyfin':
                success = JellyfinService().test_connection()
            elif service_type == 'ai':
                AIService()
                success = True 
            elif service_type == 'media':
                config = AppConfig.get_solo()
                providers = []
                if config.media_server_type in [MediaServerType.PLEX, MediaServerType.BOTH]:
                    providers.append(PlexService())
                if config.media_server_type in [MediaServerType.JELLYFIN, MediaServerType.BOTH]:
                    providers.append(JellyfinService())
                success = any(p.test_connection() for p in providers)
            else:
                success = False
        except Exception:
            success = False

        if mini:
            return render(request, 'vibarr/partials/status_badge.html', {'success': success})
            
        status_html = '<span class="text-green-500 font-bold flex items-center">Success</span>' if success else '<span class="text-rose-500 font-bold flex items-center">Error</span>'
        return HttpResponse(status_html)
        
class ResetSyncStatusView(APIMixin, View):
    def post(self, request):
        config = AppConfig.get_solo()
        config.is_syncing = False
        config.sync_status = "Sync reset by administrator."
        config.save()
        messages.success(request, "Sync status has been force-reset.")
        if request.headers.get('HX-Request'):
            return HttpResponse('<p class="text-green-500 text-xs font-bold">Status Reset Successfully</p>')
        if getattr(request, 'is_api_request', False):
            return JsonResponse({'status': 'success', 'message': 'Sync status reset'})
        return redirect('settings')

class ExternalSyncView(APIMixin, View):
    def get(self, request, *args, **kwargs):
        async_task(sync_external_states)
        
        if request.headers.get('HX-Request'):
            response = HttpResponse("")
            response['HX-Trigger'] = '{"show-toast": "Manager Health Sync: Task queued."}'
            return response

        messages.success(request, "Sonarr/Radarr monitoring health check triggered.")
        if getattr(request, 'is_api_request', False):
            return JsonResponse({'status': 'success', 'message': 'External sync triggered'})
        return redirect('settings_automation')


class RescoreShowView(View):
    def post(self, request, show_id):
        show = get_object_or_404(Show, id=show_id)
        
        try:
            rec, promoted = reevaluate_single_show(show)
        except Exception as e:
            logger.exception(f"Error during re-scoring for show '{show.title}': {e}")
            if request.headers.get('HX-Request'):
                if show.state == ShowState.SUGGESTED:
                    response = render(request, 'vibarr/partials/discovery_card.html', {
                        'show': show,
                        'flipped': True
                    })
                elif show.state == ShowState.TASTING:
                    response = render(request, 'vibarr/partials/active_tastings.html', {
                        'tasting': [show],
                        'flipped': True
                    })
                else:
                    response = HttpResponse(HTMX_REMOVE)
                response['HX-Trigger'] = json.dumps({
                    'show-toast': {
                        'message': f"Failed to re-score '{show.title}': {str(e)}",
                        'type': 'error'
                    }
                })
                return response
            else:
                messages.error(request, f"Failed to re-score '{show.title}': {str(e)}")
                return redirect('dashboard')

        if request.headers.get('HX-Request'):
            if promoted:
                response = HttpResponse(HTMX_REMOVE)
                response['HX-Trigger'] = json.dumps({
                    'discovery-changed': '',
                    'tasting-changed': '',
                    'show-toast': {
                        'message': f"'{show.title}' promoted to Auto-Tasting!",
                        'type': 'success'
                    }
                })
                return response
            
            if show.state == ShowState.SUGGESTED:
                response = render(request, 'vibarr/partials/discovery_card.html', {
                    'show': show,
                    'flipped': True
                })
            elif show.state == ShowState.TASTING:
                response = render(request, 'vibarr/partials/active_tastings.html', {
                    'tasting': [show],
                    'flipped': True
                })
            else:
                response = HttpResponse(HTMX_REMOVE)
                
            response['HX-Trigger'] = json.dumps({
                'show-toast': {
                    'message': f"Re-scored '{show.title}' successfully.",
                    'type': 'success'
                }
            })
            return response
            
        if promoted:
            messages.success(request, f"'{show.title}' score updated and promoted to Auto-Tasting.")
        else:
            messages.success(request, f"Re-scored '{show.title}' successfully.")
        return redirect('dashboard')


