from django.views.generic import TemplateView, View
from django.shortcuts import render
from django.http import HttpResponse
from .mixins import ConfigMixin
from ..models import AppConfig, Show, ShowState, MediaServerType
from ..services.discovery.ai_service import AIService
from ..services.discovery.tmdb_service import TMDBService
from ..services.media.plex_service import PlexService
from ..services.media.jellyfin_service import JellyfinService
from django_q.tasks import async_task

class VibeSearchView(ConfigMixin, TemplateView):
    template_name = 'vibarr/search.html'

class VibeSearchActionView(View):
    def post(self, request, *args, **kwargs):
        query = request.POST.get('q')
        if not query:
            return HttpResponse("")
            
        ai = AIService()
        tmdb = TMDBService()
        config = AppConfig.objects.first()
        
        # Get providers for library filtering
        providers = []
        if config.media_server_type in [MediaServerType.PLEX, MediaServerType.BOTH]:
            providers.append(PlexService())
        if config.media_server_type in [MediaServerType.JELLYFIN, MediaServerType.BOTH]:
            providers.append(JellyfinService())
            
        library_titles = []
        for p in providers:
            library_titles.extend([t.lower() for t in p.get_library_titles()])
        library_titles = list(set(library_titles))
        
        # 1. Get titles from AI
        raw_suggestions = ai.vibe_search(query)
        
        # 2. Enrich with TMDB data
        enriched_results = []
        for sug in raw_suggestions:
            title = sug['title']
            is_movie = sug['media_type'] == 'MOVIE'
            
            if title.lower() in library_titles:
                continue
                
            search_res = tmdb.search_movie(title) if is_movie else tmdb.search_show(title)
            if search_res:
                details = tmdb.get_movie_details(search_res['id']) if is_movie else tmdb.get_show_details(search_res['id'])
                enriched_results.append({
                    'id': search_res['id'],
                    'tmdb_id': search_res['id'],
                    'title': search_res.get('name') or search_res.get('title'),
                    'poster_path': search_res.get('poster_path'),
                    'media_type': 'MOVIE' if is_movie else 'SHOW',
                    'reasoning': sug.get('reasoning'),
                    'vote_average': search_res.get('vote_average', 0),
                    'content_rating': details.get('content_rating', 'NR')
                })

        return render(request, 'vibarr/partials/vibe_search_results.html', {
            'results': enriched_results,
            'query': query
        })

class TasteFromSearchView(View):
    def post(self, request, *args, **kwargs):
        tmdb_id = request.POST.get('tmdb_id')
        media_type = request.POST.get('media_type')
        title = request.POST.get('title')
        
        show, created = Show.objects.get_or_create(
            tmdb_id=tmdb_id,
            defaults={
                'title': title,
                'media_type': media_type,
                'state': ShowState.SUGGESTED
            }
        )
        
        from ..tasks import start_tasting
        async_task(start_tasting, show.id)
        
        return HttpResponse(f'<div class="bg-green-500/20 text-green-500 p-2 rounded text-[10px] text-center font-bold">Added to {media_type} manager</div>')
