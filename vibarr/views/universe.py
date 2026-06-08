from django.views.generic import ListView, View
from django.shortcuts import render, redirect
from django.db.models import Count, Q
from django.contrib import messages
from django_q.tasks import async_task
from .mixins import ConfigMixin
from ..models import Show, ShowState, MediaType
from ..models.universe import Universe, UniverseMergeSuggestion
from ..services.managers.sonarr_service import SonarrService
from ..services.managers.radarr_service import RadarrService
from django.http import HttpResponse
import json

class UniverseListView(ConfigMixin, ListView):
    model = Show
    template_name = 'vibarr/universe.html'
    context_object_name = 'universes'
    
    def get_template_names(self):
        if self.request.GET.get('partial') == 'true':
            return ['vibarr/partials/universe_list.html']
        return [self.template_name]

    def get_queryset(self):
        # Prefetch shows and recommendations to prevent N+1 queries
        universes_qs = Universe.objects.prefetch_related('shows__recommendations').all()
        
        # Enrich with download status from Managers
        sonarr = SonarrService()
        radarr = RadarrService()
        s_queue = sonarr.get_full_queue()
        r_queue = radarr.get_full_queue()
        
        s_queued_ids = {item.get('seriesId') for item in s_queue if item.get('seriesId')}
        r_queued_ids = {item.get('movieId') for item in r_queue if item.get('movieId')}

        sorted_universes = []
        for universe in universes_qs:
            shows = list(universe.shows.all())
            if not shows:
                continue
                
            for show in shows:
                if show.media_type == MediaType.SHOW:
                    show.is_downloading = show.sonarr_id in s_queued_ids
                else:
                    show.is_downloading = show.radarr_id in r_queued_ids
            
            sorted_universes.append({
                'id': universe.id,
                'name': universe.name,
                'items': shows,
                'count': len(shows)
            })
            
        sorted_universes = sorted(
            sorted_universes,
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
        from django.core.cache import cache
        context['alphabet'] = list(string.ascii_uppercase) + ['#']
        context['active_letters'] = getattr(self, 'active_letters', set())
        context['suggestions'] = UniverseMergeSuggestion.objects.select_related('source_universe', 'target_universe').all()
        context['all_universes'] = Universe.objects.all()
        context['scan_running'] = cache.get('universe_scan_running', False)
        context['scan_progress'] = cache.get('universe_scan_progress', 0)
        context['scan_status'] = cache.get('universe_scan_status', '')
        return context

class CompleteUniverseView(ConfigMixin, View):
    def post(self, request):
        universe_name = request.POST.get('universe')
        if not universe_name:
            return redirect('universe_architect_list')
            
        # Get all suggested items in this universe
        suggested = Show.objects.filter(
            universes__name=universe_name,
            state=ShowState.SUGGESTED
        ).distinct()
        
        count = 0
        for show in suggested:
            show.state = ShowState.TASTING
            show.save()
            async_task('vibarr.tasks.managers.actions.start_tasting', show.id)
            count += 1
            
        messages.success(request, f"Added {count} items from '{universe_name}' to your tasting queue.")
        return redirect('universe_architect_list')

class RemoveFromUniverseView(ConfigMixin, View):
    def post(self, request, show_id):
        try:
            show = Show.objects.get(id=show_id)
            universe_name = request.POST.get('universe') or request.GET.get('universe')
            
            if universe_name:
                try:
                    universe = Universe.objects.get(name=universe_name)
                    show.universes.remove(universe)
                    
                    if not show.universes.exists():
                        show.universe_name = None
                        show.save()
                        
                    msg = f"Removed '{show.title}' from '{universe_name}'."
                except Universe.DoesNotExist:
                    msg = f"Universe '{universe_name}' not found."
            else:
                show.universes.clear()
                show.universe_name = None
                show.save()
                msg = f"Removed '{show.title}' from all universes."
                
            if request.headers.get('HX-Request'):
                response = HttpResponse("")
                response['HX-Trigger'] = json.dumps({
                    'show-toast': {
                        'message': msg,
                        'type': 'success'
                    }
                })
                return response
                
            messages.success(request, msg)
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
        show = Show.objects.filter(universes__name=universe_name).order_by('-state', '-updated_at').distinct().first()
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

class MergeUniversesView(ConfigMixin, View):
    def post(self, request):
        source_name = request.POST.get('source_universe')
        target_name = request.POST.get('target_universe')
        custom_target = request.POST.get('custom_target_universe')
        
        if not source_name:
            messages.error(request, "Source universe is required.")
            return redirect('universe_architect_list')
            
        final_target_name = custom_target.strip() if custom_target else target_name
        if not final_target_name:
            messages.error(request, "Target universe or a new name is required.")
            return redirect('universe_architect_list')
            
        if source_name == final_target_name:
            messages.error(request, "Source and Target universes cannot be the same.")
            return redirect('universe_architect_list')
            
        try:
            source_universe = Universe.objects.get(name=source_name)
        except Universe.DoesNotExist:
            messages.error(request, f"Source universe '{source_name}' does not exist.")
            return redirect('universe_architect_list')
            
        target_universe, created = Universe.objects.get_or_create(name=final_target_name)
        
        shows = source_universe.shows.all()
        count = shows.count()
        for show in shows:
            show.universes.add(target_universe)
            show.universes.remove(source_universe)
            if show.universe_name == source_name:
                show.universe_name = final_target_name
                show.save()
                
        source_universe.delete()
        
        UniverseMergeSuggestion.objects.filter(
            Q(source_universe__name=source_name) | 
            Q(target_universe__name=source_name) |
            Q(source_universe__name=final_target_name) |
            Q(target_universe__name=final_target_name)
        ).delete()
        
        msg = f"Merged '{source_name}' into '{final_target_name}'. Re-mapped {count} items."
        
        if request.headers.get('HX-Request'):
            response = HttpResponse("")
            response['HX-Trigger'] = json.dumps({
                'show-toast': {
                    'message': msg,
                    'type': 'success'
                },
                'refresh-universes': {}
            })
            return response
            
        messages.success(request, msg)
        return redirect('universe_architect_list')

class AnalyzeEcosystemView(ConfigMixin, View):
    def post(self, request):
        from django.core.cache import cache
        
        cache.set('universe_scan_running', True, 300)
        cache.set('universe_scan_progress', 0, 300)
        cache.set('universe_scan_status', 'Initializing AI Ecosystem analysis...', 300)
        
        async_task('vibarr.tasks.managers.sync.analyze_universe_ecosystem_task')
        
        if request.headers.get('HX-Request'):
            return render(request, 'vibarr/partials/universe_scan_status.html', {
                'running': True,
                'progress': 0,
                'status': 'Initializing AI Ecosystem analysis...'
            })
            
        messages.success(request, "AI Ecosystem analysis triggered in background.")
        return redirect('universe_architect_list')

class UniverseScanStatusView(ConfigMixin, View):
    def get(self, request):
        from django.core.cache import cache
        
        running = cache.get('universe_scan_running', False)
        progress = cache.get('universe_scan_progress', 0)
        status = cache.get('universe_scan_status', '')
        
        response = render(request, 'vibarr/partials/universe_scan_status.html', {
            'running': running,
            'progress': progress,
            'status': status
        })
        
        if not running:
            response['HX-Trigger'] = 'refresh-universes'
            
        return response

class DismissSuggestionView(ConfigMixin, View):
    def post(self, request, suggestion_id):
        try:
            sug = UniverseMergeSuggestion.objects.get(id=suggestion_id)
            sug_text = f"{sug.source_universe.name} → {sug.target_universe.name}"
            sug.delete()
            
            msg = f"Dismissed alignment suggestion: {sug_text}"
            if request.headers.get('HX-Request'):
                response = HttpResponse("")
                response['HX-Trigger'] = json.dumps({
                    'show-toast': {
                        'message': msg,
                        'type': 'success'
                    }
                })
                return response
                
            messages.success(request, msg)
            return redirect('universe_architect_list')
        except UniverseMergeSuggestion.DoesNotExist:
            if request.headers.get('HX-Request'):
                return HttpResponse(status=404)
            return redirect('universe_architect_list')



