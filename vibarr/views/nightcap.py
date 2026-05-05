from django.views.generic import TemplateView, View
from django.shortcuts import render
from ..services.discovery.ai_service import AIService
from ..services.discovery.tmdb_service import TMDBService
from ..models import MediaWatchEvent, Show, ShowState, MediaType
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)

class NightcapView(View):
    def get(self, request):
        # Determine the current contextual mood
        now = timezone.now()
        hour = now.hour
        day = now.weekday()
        
        moods = []
        if 0 <= hour < 5:
            moods = ["Late Night Chill", "Mindless Background", "Horror Hour"]
        elif 5 <= hour < 11:
            moods = ["Morning Coffee", "Educational", "Inspiring"]
        elif 11 <= hour < 17:
            moods = ["Lunch Break", "Productive Vibes", "Lighthearted"]
        elif 17 <= hour < 22:
            moods = ["Prime Time", "Cinematic", "Trending Now"]
        else:
            moods = ["The Nightcap", "Sleepy Time", "Gritty Noir"]
            
        return render(request, 'vibarr/partials/nightcap_widget.html', {'moods': moods})

class NightcapActionView(View):
    def post(self, request):
        mood = request.POST.get('mood')
        ai = AIService()
        tmdb = TMDBService()
        
        # Get recent history for context
        history = MediaWatchEvent.objects.order_by('-watched_at').values_list('show_title', flat=True).distinct()[:10]
        
        recommendations = ai.get_mood_recommendations(list(history), mood)
        
        results = []
        for rec in recommendations:
            # Try to get TMDB details for posters
            is_movie = rec['media_type'] == 'MOVIE'
            search = tmdb.search_movie(rec['title']) if is_movie else tmdb.search_show(rec['title'])
            providers = tmdb.get_watch_providers(search['id'], is_movie=is_movie) if search else []
            results.append({
                'title': rec['title'],
                'media_type': rec['media_type'],
                'reasoning': rec['reasoning'],
                'vibe_tags': rec['vibe_tags'],
                'poster_path': search['poster_path'] if search else None,
                'tmdb_id': search['id'] if search else None,
                'providers': providers
            })
            
        return render(request, 'vibarr/partials/nightcap_results.html', {
            'results': results,
            'mood': mood
        })
