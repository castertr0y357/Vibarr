from django.views.generic import ListView, View
from django.shortcuts import render, redirect
from django.db.models import Count
from django.contrib import messages
from django_q.tasks import async_task
from .mixins import ConfigMixin
from ..models import Show, ShowState

class UniverseListView(ConfigMixin, ListView):
    model = Show
    template_name = 'vibarr/universe.html'
    context_object_name = 'universes'
    
    def get_template_names(self):
        if self.request.GET.get('partial') == 'true':
            return ['vibarr/partials/universe_list.html']
        return [self.template_name]

    def get_queryset(self):
        # We want to group by universe_name and only include those with items
        qs = Show.objects.filter(universe_name__isnull=False).exclude(universe_name='')
        
        # We'll return a dictionary or a list of dictionaries grouped by universe_name
        universes = {}
        for show in qs.prefetch_related('recommendations'):
            u_name = show.universe_name
            if u_name not in universes:
                universes[u_name] = []
            universes[u_name].append(show)
            
        # Convert to a list of dicts for easier template iteration
        # Sort by count of items DESC
        return sorted(
            [{'name': k, 'items': v, 'count': len(v)} for k, v in universes.items()],
            key=lambda x: x['count'],
            reverse=True
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context

class CompleteUniverseView(ConfigMixin, View):
    def post(self, request):
        universe_name = request.POST.get('universe')
        if not universe_name:
            return redirect('universe_architect_list')
            
        # Get all suggested items in this universe
        suggested = Show.objects.filter(
            universe_name=universe_name,
            state=ShowState.SUGGESTED
        )
        
        count = 0
        for show in suggested:
            show.state = ShowState.TASTING
            show.save()
            async_task('vibarr.tasks.managers.actions.start_tasting', show.id)
            count += 1
            
        messages.success(request, f"Added {count} items from '{universe_name}' to your tasting queue.")
        return redirect('universe_architect_list')
