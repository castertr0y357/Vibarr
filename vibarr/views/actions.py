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

logger = logging.getLogger(__name__)

# Return an empty string, allowing hx-swap="delete" to remove the element without DOM clutter
HTMX_REMOVE = ""

class RejectShowView(View):
    def post(self, request, show_id):
        show = get_object_or_404(Show, id=show_id)
        show.state = ShowState.REJECTED
        show.save()
        if request.headers.get('HX-Request'):
            return HttpResponse(HTMX_REMOVE)
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
            return HttpResponse(HTMX_REMOVE)
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
            return HttpResponse(HTMX_REMOVE)
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
            oob = f'<div id="active-tastings-container" hx-swap-oob="true" hx-get="{dashboard_url}" hx-trigger="sync-complete from:body" hx-sync="this:replace" hx-indicator="#tasting-indicator" class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-6">{html}</div>'
            return HttpResponse(oob)
            
        messages.info(request, f"Started tasting for '{show.title}'.")
        return redirect('dashboard')

class ManualSyncView(APIMixin, RedirectView):
    pattern_name = 'dashboard'
    def get(self, request, *args, **kwargs):
        config = AppConfig.get_solo()
        config.is_syncing = True
        config.sync_status = "Sync task queued..."
        config.save()
        
        async_task(poll_media_servers, hours=72)
        async_task(sync_external_states)
        messages.success(request, "Manual sync triggered.")
        if getattr(request, 'is_api_request', False):
            return JsonResponse({'status': 'success', 'message': 'Manual sync triggered'})
        return super().get(request, *args, **kwargs)

class UniverseSyncView(APIMixin, RedirectView):
    pattern_name = 'dashboard'
    def get(self, request, *args, **kwargs):
        async_task(batch_universe_sync)
        messages.success(request, "Universe Architect: Batch sync triggered for all committed items.")
        if getattr(request, 'is_api_request', False):
            return JsonResponse({'status': 'success', 'message': 'Batch universe sync triggered'})
        return super().get(request, *args, **kwargs)

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

