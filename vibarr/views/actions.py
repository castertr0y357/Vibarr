from django.views.generic import View, RedirectView
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django_q.tasks import async_task
from ..models import Show, ShowState, AppConfig, MediaServerType
from ..services.managers.sonarr_service import SonarrService
from ..services.managers.radarr_service import RadarrService
from ..services.media.plex_service import PlexService
from ..services.media.jellyfin_service import JellyfinService
from ..services.discovery.ai_service import AIService
from .mixins import ConfigMixin, APIMixin
import logging

class RejectShowView(APIMixin, View):
    def post(self, request, show_id):
        show = get_object_or_404(Show, id=show_id)
        show.state = ShowState.REJECTED
        show.save()
        if request.headers.get('HX-Request'):
            return HttpResponse("")
        if getattr(request, 'is_api_request', False):
            return JsonResponse({'status': 'success', 'message': f'Show {show_id} rejected'})
        return redirect('dashboard')

class TogglePinShowView(View):
    def post(self, request, show_id):
        show = get_object_or_404(Show, id=show_id)
        show.is_pinned = not show.is_pinned
        show.save()
        if request.headers.get('HX-Request'):
            from django.shortcuts import render
            return render(request, 'vibarr/partials/pin_button.html', {'show': show})
        return redirect('dashboard')

class StopAndDeleteShowView(View):
    def post(self, request, show_id):
        show = get_object_or_404(Show, id=show_id)
        if show.sonarr_id:
            try: SonarrService().delete_series(show.sonarr_id)
            except Exception as e: logger.error(f"Sonarr delete error: {e}")
        if show.radarr_id:
            try: RadarrService().delete_movie(show.radarr_id)
            except Exception as e: logger.error(f"Radarr delete error: {e}")
        
        show.state = ShowState.REJECTED
        show.save()
        if request.headers.get('HX-Request'):
            return HttpResponse("")
        return redirect('dashboard')

class MarkWatchedView(APIMixin, View):
    def post(self, request, show_id):
        show = get_object_or_404(Show, id=show_id)
        show.state = ShowState.WATCHED
        show.save()
        
        # Inform history to avoid re-suggesting
        from ..models import MediaWatchEvent
        MediaWatchEvent.objects.get_or_create(
            event_id=f"MANUAL_{show.tmdb_id}",
            defaults={
                'source_server': 'MANUAL',
                'show_title': show.title,
                'tmdb_id': show.tmdb_id,
                'media_type': show.media_type,
                'watched_at': timezone.now(),
            }
        )
        
        if request.headers.get('HX-Request'):
            return HttpResponse("")
        return redirect('dashboard')

class TasteShowView(APIMixin, View):
    def post(self, request, show_id):
        show = get_object_or_404(Show, id=show_id)
        from ..tasks import start_tasting
        async_task(start_tasting, show.id)
        messages.info(request, f"Started tasting for '{show.title}'.")
        if request.headers.get('HX-Request'):
            return HttpResponse("")
        if getattr(request, 'is_api_request', False):
            return JsonResponse({'status': 'success', 'message': f'Started tasting for {show.title}'})
        return redirect('dashboard')

class ManualSyncView(APIMixin, RedirectView):
    pattern_name = 'dashboard'
    def get(self, request, *args, **kwargs):
        from ..tasks import poll_media_servers, sync_external_states
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
        from ..tasks.managers.sync import batch_universe_sync
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
                # Simplified check
                AIService()
                success = True # or actual ping
            elif service_type == 'media':
                config = AppConfig.objects.first()
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
            color = "bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]" if success else "bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.6)]"
            return HttpResponse(f'<div class="w-1.5 h-1.5 rounded-full {color}"></div>')
        
        status_html = '<span class="text-green-500 font-bold flex items-center">Success</span>' if success else '<span class="text-rose-500 font-bold flex items-center">Error</span>'
        return HttpResponse(status_html)
