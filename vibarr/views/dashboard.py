from django.views.generic import TemplateView
from .mixins import ConfigMixin
from ..models import Show, ShowState, MediaServerType
from ..services.managers.sonarr_service import SonarrService
from ..services.managers.radarr_service import RadarrService
from ..services.media.jellyfin_service import JellyfinService

from .mixins import APIMixin

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
        
        # Prefetch recommendations and watch events
        context['suggested'] = Show.objects.filter(
            state=ShowState.SUGGESTED
        ).prefetch_related('recommendations').order_by('-is_pinned', '-recommendations__score')[:20]
        context['tasting'] = Show.objects.filter(state=ShowState.TASTING).prefetch_related('mediawatchevent_set')
        context['committed'] = Show.objects.filter(state=ShowState.COMMITTED).order_by('-updated_at')[:10]
        
        # Determine if we should render a partial
        partial = self.request.GET.get('partial')
        if partial == 'discovery':
            self.template_name = 'vibarr/partials/discovery_feed.html'
        elif partial == 'tasting':
            self.template_name = 'vibarr/partials/active_tastings.html'
        elif partial == 'committed':
            self.template_name = 'vibarr/partials/recent_committed.html'
            
        from ..models import Persona
        context['personas'] = Persona.objects.all()
        return context

    def get(self, request, *args, **kwargs):
        # Override get to handle template switching for HTMX partials
        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)
