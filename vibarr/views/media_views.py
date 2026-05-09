from django.views.generic import ListView
from django.shortcuts import render
from .mixins import ConfigMixin
from ..models import Show, ShowState, MediaType

class DiscoveryListView(ConfigMixin, ListView):
    model = Show
    template_name = 'vibarr/discovery_list.html'
    context_object_name = 'suggested'

    def get(self, request, *args, **kwargs):
        if request.headers.get('HX-Request'):
            self.template_name = 'vibarr/partials/discovery_feed.html'
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        qs = Show.objects.filter(state=ShowState.SUGGESTED).prefetch_related('recommendations')
        media_type = self.request.GET.get('media_type')
        if media_type in ['MOVIE', 'SHOW']:
            qs = qs.filter(media_type=media_type)
        return qs.order_by('-is_pinned', '-recommendations__score')

class TastingListView(ConfigMixin, ListView):
    model = Show
    template_name = 'vibarr/tasting_list.html'
    context_object_name = 'tasting'

    def get_queryset(self):
        # We need to sort by a property, so we convert to a list
        qs = Show.objects.filter(state=ShowState.TASTING).prefetch_related('mediawatchevent_set', 'recommendations')
        all_tastings = list(qs)
        all_tastings.sort(key=lambda s: (s.tasting_progress_percent, s.recommendations.first().score if s.recommendations.exists() else 0), reverse=True)
        return all_tastings

class CommittedListView(ConfigMixin, ListView):
    model = Show
    template_name = 'vibarr/committed_list.html'
    context_object_name = 'committed'

    def get_queryset(self):
        return Show.objects.filter(state=ShowState.COMMITTED, media_type=MediaType.SHOW).prefetch_related('recommendations').order_by('-updated_at')
