import logging
import math
from django.db.models import Max, Count
from ...models import AppConfig, MediaWatchEvent, ShowState, MediaType, Show
from ..managers.seerr_service import SeerrService
from ..discovery.tmdb_service import TMDBService

logger = logging.getLogger(__name__)

class HeuristicRankingService:
    def __init__(self, config=None):
        self.config = config or AppConfig.get_solo()
        self.tmdb = TMDBService()

    def rank_candidates(self, target_type, candidates):
        """
        Ranks candidates using weighted heuristic matching.
        Returns a list of objects with 'title', 'score', 'reasoning', and 'vibe_tags'.
        """
        # 1. Build User Profile
        profile = self._build_user_profile(target_type)
        
        # 2. Fetch Seerr Profile (Optional)
        seerr_profile = self._build_seerr_profile() if self.config.use_seerr else set()

        ranked_results = []
        for candidate in candidates:
            score_data = self._calculate_score(candidate, target_type, profile, seerr_profile)
            ranked_results.append(score_data)

        # Sort by score descending
        ranked_results.sort(key=lambda x: x['score'], reverse=True)
        return ranked_results

    def _build_user_profile(self, target_type):
        """
        Analyzes history to find preferred genres and keywords.
        Blends the top 10 most recent unique items and the top 10 overall most played items.
        """
        base_query = MediaWatchEvent.objects.filter(
            media_type=target_type,
            tmdb_id__isnull=False
        ).values('tmdb_id').annotate(
            latest_watch=Max('watched_at'),
            play_count=Count('id')
        )
        
        recent_history = list(base_query.order_by('-latest_watch')[:10])
        top_history = list(base_query.order_by('-play_count', '-latest_watch')[:10])
        
        seen_ids = set()
        unique_history = []
        for item in recent_history:
            if item['tmdb_id'] not in seen_ids:
                seen_ids.add(item['tmdb_id'])
                unique_history.append(item)
        for item in top_history:
            if item['tmdb_id'] not in seen_ids:
                seen_ids.add(item['tmdb_id'])
                unique_history.append(item)
        
        genres = {}
        keywords = {}
        collections = set()
        genre_names = {}
        keyword_names = {}
        
        for item in unique_history:
            tmdb_id = item['tmdb_id']
            play_count = item['play_count']
            
            # Apply logarithmic scaling to play count: weight = 1.0 + ln(play_count)
            weight = 1.0 + math.log(play_count)
            
            details = self.tmdb.get_movie_details(tmdb_id) if target_type == MediaType.MOVIE else self.tmdb.get_show_details(tmdb_id)
            
            if details:
                # Genres
                for g in details.get('genres', []):
                    genres[g['id']] = genres.get(g['id'], 0.0) + weight
                    genre_names[g['id']] = g['name']
                
                # Keywords
                kw_key = 'keywords' if target_type == MediaType.MOVIE else 'results'
                for k in details.get('keywords', {}).get(kw_key, []):
                    keywords[k['id']] = keywords.get(k['id'], 0.0) + weight
                    keyword_names[k['id']] = k['name']
                
                # Collection
                if target_type == MediaType.MOVIE and details.get('belongs_to_collection'):
                    collections.add(details['belongs_to_collection']['id'])

        # Apply negative keyword weights from rejected shows
        rejected = Show.objects.filter(
            state=ShowState.REJECTED,
            media_type=target_type
        ).order_by('-updated_at')[:10]
        
        for r_show in rejected:
            details = self.tmdb.get_movie_details(r_show.tmdb_id) if target_type == MediaType.MOVIE else self.tmdb.get_show_details(r_show.tmdb_id)
            if details:
                kw_key = 'keywords' if target_type == MediaType.MOVIE else 'results'
                for k in details.get('keywords', {}).get(kw_key, []):
                    keywords[k['id']] = keywords.get(k['id'], 0.0) - 1.0
                    keyword_names[k['id']] = k['name']

        return {
            'genres': genres,
            'keywords': keywords,
            'collections': collections,
            'genre_names': genre_names,
            'keyword_names': keyword_names
        }

    def _build_seerr_profile(self):
        """
        Gets keywords/genres from items requested in Seerr.
        """
        seerr = SeerrService()
        requests = seerr.get_requests()
        seerr_ids = {r.get('media', {}).get('tmdbId') for r in requests if r.get('media', {}).get('tmdbId')}
        return seerr_ids

    def _calculate_score(self, candidate, target_type, profile, seerr_profile):
        """
        Calculates a score from 0 to 10 for a candidate.
        """
        is_movie = target_type == MediaType.MOVIE
        
        # Base stats
        rating = candidate.get('vote_average', 0) # 0-10
        popularity = min(candidate.get('popularity', 0) / 100, 10) # Normalized roughly
        
        # Detailed matching (requires fetching details if not present)
        # Optimization: Candidate already has genre_ids from search results
        genre_score = 0
        candidate_genres = candidate.get('genre_ids', [])
        for g_id in candidate_genres:
            if g_id in profile['genres']:
                genre_score += profile['genres'][g_id]
        genre_score = min(genre_score * 2, 10) # Normalize

        # Keywords and Collections require full details
        details = self.tmdb.get_movie_details(candidate['id']) if is_movie else self.tmdb.get_show_details(candidate['id'])
        
        keyword_score = 0
        collection_match = 0
        vibe_tags = []
        
        if details:
            # Keyword matching
            kw_key = 'keywords' if is_movie else 'results'
            candidate_keywords = details.get('keywords', {}).get(kw_key, [])
            for k in candidate_keywords:
                if k['id'] in profile['keywords']:
                    keyword_score += profile['keywords'][k['id']]
                if len(vibe_tags) < 4:
                    vibe_tags.append(k['name'].capitalize())
            # Cap keyword score between -5.0 and 10.0
            keyword_score = max(-5.0, min(keyword_score, 10.0))
            
            # Collection matching
            if is_movie and details.get('belongs_to_collection'):
                if details['belongs_to_collection']['id'] in profile['collections']:
                    collection_match = 10
            
            # Genres from details (more accurate)
            vibe_tags.extend([g['name'] for g in details.get('genres', []) if g['name'] not in vibe_tags][:2])

        # Seerr Match
        seerr_match = 10 if candidate['id'] in seerr_profile else 0

        # Weighted calculation
        # Normalize weights to sum to 10
        w_total = (self.config.h_rating_weight + self.config.h_popularity_weight + 
                   self.config.h_genre_weight + self.config.h_keyword_weight + 
                   self.config.h_seerr_weight + self.config.h_collection_weight) or 1
        
        final_score = (
            (rating * self.config.h_rating_weight) +
            (popularity * self.config.h_popularity_weight) +
            (genre_score * self.config.h_genre_weight) +
            (keyword_score * self.config.h_keyword_weight) +
            (seerr_match * self.config.h_seerr_weight) +
            (collection_match * self.config.h_collection_weight)
        ) / w_total

        # Reasoning
        reasons = []
        if genre_score > 5: reasons.append("matches your favorite genres")
        if keyword_score > 5: reasons.append("shares thematic elements with your history")
        if seerr_match > 0: reasons.append("is trending in your request history")
        if collection_match > 0: reasons.append("is part of a collection you follow")
        
        reasoning = "This title " + (" and ".join(reasons) if reasons else "matches your general viewing patterns") + "."

        return {
            'title': candidate['title'],
            'score': round(final_score, 1),
            'reasoning': reasoning,
            'vibe_tags': vibe_tags[:4]
        }
