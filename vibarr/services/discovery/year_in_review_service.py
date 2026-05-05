import logging
from django.db.models import Count, Sum
from django.utils import timezone
from datetime import datetime
from ...models import MediaWatchEvent, Show
from .ai_service import AIService

logger = logging.getLogger(__name__)

class YearInReviewService:
    def __init__(self, year=None):
        self.year = year or timezone.now().year
        self.ai_service = AIService()

    def get_stats(self):
        events = MediaWatchEvent.objects.filter(watched_at__year=self.year)
        
        total_episodes = events.count()
        total_time_ms = events.aggregate(total=Sum('duration'))['total'] or 0
        total_hours = round(total_time_ms / (1000 * 60 * 60), 1)
        
        top_shows = events.values('show_title').annotate(
            watch_count=Count('id')
        ).order_by('-watch_count')[:5]
        
        # Monthly distribution
        monthly_data = events.extra(select={'month': "strftime('%m', watched_at)"}).values('month').annotate(
            count=Count('id')
        ).order_by('month')
        
        return {
            'year': self.year,
            'total_episodes': total_episodes,
            'total_hours': total_hours,
            'top_shows': list(top_shows),
            'monthly_data': list(monthly_data)
        }

    def generate_narrative(self, stats):
        if stats['total_episodes'] == 0:
            return "Your screens were dark this year. Time to find a new vibe?"

        top_titles = [s['show_title'] for s in stats['top_shows']]
        
        prompt = f"""
        Analyze these viewing habits for the year {self.year}:
        - Total episodes watched: {stats['total_episodes']}
        - Total time: {stats['total_hours']} hours
        - Top shows: {', '.join(top_titles)}
        
        Write a 3-4 sentence 'Year in Review' narrative. 
        Be witty, cinematic, and descriptive. Identify the 'vibe' of their year.
        (e.g., 'Your year was a slow-burn descent into neo-noir mysteries, with a surprising detour into 90s sitcom comfort...')
        """
        
        return self.ai_service.get_simple_narrative(prompt)
