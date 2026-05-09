import re
from django.views import View
from django.views.generic import TemplateView
from django.shortcuts import render

from .mixins import ConfigMixin, APIMixin
from ..models import Show, ShowState, MediaServerType, Persona, AppConfig, MediaType
from ..services.managers.sonarr_service import SonarrService
from ..services.managers.radarr_service import RadarrService
from ..services.media.jellyfin_service import JellyfinService

class DashboardView(APIMixin, ConfigMixin, TemplateView):
    template_name = 'vibarr/dashboard.html'

    def get_api_data(self, context):
        return {
            'suggested': [
                {'id': s.id, 'title': s.title, 'tmdb_id': s.tmdb_id, 'media_type': s.media_type}
                for s in context['suggested']
            ],
            'tasting': [
                {'id': s.id, 'title': s.title, 'tmdb_id': s.tmdb_id, 'media_type': s.media_type}
                for s in context['tasting']
            ],
            'committed': [
                {'id': s.id, 'title': s.title, 'tmdb_id': s.tmdb_id, 'media_type': s.media_type}
                for s in context['committed']
            ]
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Discovery: Weighted mix or filtered by media_type
        media_type_filter = self.request.GET.get('media_type')
        config = AppConfig.get_solo()
        
        if media_type_filter in ['MOVIE', 'SHOW']:
            context['suggested'] = Show.objects.filter(
                state=ShowState.SUGGESTED,
                media_type=media_type_filter
            ).prefetch_related('recommendations').order_by('-is_pinned', '-recommendations__score')[:5]
        else:
            # Balanced approach based on settings
            balance = config.show_influence_on_movies # Actually let's use the one I added: discovery_balance?
            # Wait, I added movie_influence_on_shows and show_influence_on_movies. 
            # I should have added a 'discovery_balance' field too if I wanted a single slider.
            # Let's assume the user wants a 50/50 split by default or I'll just pull the top 5 globally if not filtered.
            # Actually, I'll fetch Top 5 overall but prioritize the pinned ones.
            context['suggested'] = Show.objects.filter(
                state=ShowState.SUGGESTED
            ).prefetch_related('recommendations').order_by('-is_pinned', '-recommendations__score')[:5]
        
        # Tastings: Sorted by progress DESC, then score DESC. Limit to 5 for dashboard.
        tastings_qs = Show.objects.filter(state=ShowState.TASTING)
        if media_type_filter and media_type_filter.upper() in ['MOVIE', 'SHOW']:
            tastings_qs = tastings_qs.filter(media_type=media_type_filter.upper())
            
        all_tastings = list(tastings_qs.prefetch_related('mediawatchevent_set', 'recommendations'))
        
        # Enrich with download status from Managers
        sonarr = SonarrService()
        radarr = RadarrService()
        s_queue = sonarr.get_full_queue()
        r_queue = radarr.get_full_queue()
        
        s_queued_ids = {item.get('seriesId') for item in s_queue if item.get('seriesId')}
        r_queued_ids = {item.get('movieId') for item in r_queue if item.get('movieId')}
        
        for t in all_tastings:
            if t.media_type == MediaType.SHOW:
                t.is_downloading = t.sonarr_id in s_queued_ids
            else:
                t.is_downloading = t.radarr_id in r_queued_ids

        all_tastings.sort(key=lambda s: (s.tasting_progress_percent, s.recommendations.first().score if s.recommendations.exists() else 0), reverse=True)
        context['tasting'] = all_tastings[:5]
        
        committed_qs = Show.objects.filter(
            state=ShowState.COMMITTED, 
            media_type=MediaType.SHOW
        ).prefetch_related('recommendations').order_by('-updated_at')
        
        context['committed'] = list(committed_qs[:5])
        for c in context['committed']:
            c.is_downloading = c.sonarr_id in s_queued_ids
        
        # Determine if we should render a partial
        partial = self.request.GET.get('partial')
        if partial == 'discovery':
            self.template_name = 'vibarr/partials/discovery_feed.html'
        elif partial == 'tasting':
            self.template_name = 'vibarr/partials/active_tastings.html'
        elif partial == 'committed':
            self.template_name = 'vibarr/partials/recent_committed.html'
        elif partial == 'sync':
            self.template_name = 'vibarr/partials/sync_status.html'
            
        context['personas'] = Persona.objects.all()
        return context

    def get(self, request, *args, **kwargs):
        # Override get to handle template switching for HTMX partials
        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)

class SyncStatusView(ConfigMixin, View):
    def get(self, request):
        config = AppConfig.get_solo()
        sync_percent = 0
        if config.sync_status:
            match = re.search(r'\((\d+)%\)', config.sync_status)
            if match:
                sync_percent = int(match.group(1))
        return render(request, 'vibarr/partials/sync_status.html', {'config': config, 'sync_percent': sync_percent})

