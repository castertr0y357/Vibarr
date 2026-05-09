from .ai.universe import AIUniverseService
from .ai.ranking import AIRankingService
from .ai.search import AISearchService

class AIService:
    """Composite service for AI features. Re-exports methods from specialized services."""
    def __init__(self, config=None):
        self.universe = AIUniverseService(config)
        self.ranking = AIRankingService(config)
        self.search = AISearchService(config)

    def identify_universe(self, title):
        return self.universe.identify_universe(title)

    def identify_cross_media_bridge(self, title, media_type):
        return self.universe.identify_cross_media_bridge(title, media_type)

    def vibe_search(self, query):
        return self.search.vibe_search(query)

    def get_simple_narrative(self, prompt):
        return self.search.get_simple_narrative(prompt)

    def rank_shows(self, history_titles, candidates, context=None):
        return self.ranking.rank_shows(history_titles, candidates, context)

    def score_candidates(self, history_titles, candidates):
        return self.ranking.score_candidates(history_titles, candidates)

    def get_mood_recommendations(self, history_titles, mood):
        return self.ranking.get_mood_recommendations(history_titles, mood)
