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
        
        # We'll return a list of dictionaries grouped by universe_name sorted alphabetically
        universes = {}
        for show in qs.prefetch_related('recommendations'):
            u_name = show.universe_name
            if u_name not in universes:
                universes[u_name] = []
            universes[u_name].append(show)
            
        sorted_universes = sorted(
            [{'name': k, 'items': v, 'count': len(v)} for k, v in universes.items()],
            key=lambda x: x['name'].lower()
        )

        import string
        seen_letters = set()
        active_letters = set()

        for u in sorted_universes:
            first_char = u['name'][0].upper() if u['name'] else '#'
            if first_char not in string.ascii_uppercase:
                first_char = '#'
            
            active_letters.add(first_char)
            if first_char not in seen_letters:
                u['group_letter'] = first_char
                seen_letters.add(first_char)

        self.active_letters = active_letters
        return sorted_universes

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        import string
        context['alphabet'] = list(string.ascii_uppercase) + ['#']
        context['active_letters'] = getattr(self, 'active_letters', set())
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

from django.http import HttpResponse
import json

class RemoveFromUniverseView(ConfigMixin, View):
    def post(self, request, show_id):
        try:
            show = Show.objects.get(id=show_id)
            old_universe = show.universe_name
            show.universe_name = None
            show.save()
            
            if request.headers.get('HX-Request'):
                response = HttpResponse("")
                response['HX-Trigger'] = json.dumps({
                    'show-toast': {
                        'message': f"Removed '{show.title}' from '{old_universe}'.",
                        'type': 'success'
                    }
                })
                return response
                
            messages.success(request, f"Removed '{show.title}' from '{old_universe}'.")
            return redirect('universe_architect_list')
        except Show.DoesNotExist:
            if request.headers.get('HX-Request'):
                return HttpResponse(status=404)
            return redirect('universe_architect_list')


class RefreshUniverseView(ConfigMixin, View):
    def post(self, request):
        universe_name = request.POST.get('universe')
        if not universe_name:
            return redirect('universe_architect_list')
            
        # Find a representative show in this universe
        # Prefer COMMITTED, TASTING or WATCHED, but any will do
        show = Show.objects.filter(universe_name=universe_name).order_by('-state', '-updated_at').first()
        if show:
            async_task('vibarr.tasks.managers.sync.discover_universe_and_sync', show.id)
            
            if request.headers.get('HX-Request'):
                response = HttpResponse("")
                response['HX-Trigger'] = json.dumps({
                    'show-toast': {
                        'message': f"Refresh triggered for '{universe_name}'.",
                        'type': 'success'
                    }
                })
                return response
            messages.success(request, f"Refresh triggered for '{universe_name}'.")
        else:
            messages.error(request, f"No items found in universe '{universe_name}'.")
            
        return redirect('universe_architect_list')


class ReanalyzeUniverseView(ConfigMixin, View):
    def post(self, request):
        universe_name = request.POST.get('universe')
        if not universe_name:
            return redirect('universe_architect_list')
            
        async_task('vibarr.tasks.managers.sync.reevaluate_universe_shows', universe_name)
        
        if request.headers.get('HX-Request'):
            response = HttpResponse("")
            response['HX-Trigger'] = json.dumps({
                'show-toast': {
                    'message': f"Reanalysis triggered for items in '{universe_name}'.",
                    'type': 'success'
                }
            })
            return response
        messages.success(request, f"Reanalysis triggered for items in '{universe_name}'.")
        return redirect('universe_architect_list')


