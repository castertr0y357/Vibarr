import requests
from django.conf import settings
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)

class TMDBService:
    BASE_URL = "https://api.themoviedb.org/3"
    _session = None
    
    def __init__(self):
        from ...models import AppConfig
        config = AppConfig.get_solo()
        self.api_key = config.tmdb_api_key or getattr(settings, 'TMDB_API_KEY', '')
        self.region = config.tmdb_region or "US"
        self.language = config.tmdb_language or "en-US"
        
        if TMDBService._session is None:
            TMDBService._session = requests.Session()

    def _get(self, endpoint, params=None, cache_key=None, ttl=3600):
        if cache_key:
            cached = cache.get(cache_key)
            if cached: return cached

        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        final_params = {"api_key": self.api_key}
        if params: final_params.update(params)
        
        try:
            response = self._session.get(url, params=final_params, timeout=10)
            response.raise_for_status()
            data = response.json()
            if cache_key: cache.set(cache_key, data, ttl)
            return data
        except Exception as e:
            logger.error(f"TMDB Error [{endpoint}]: {e}")
            return None

    def search_show(self, title):
        cache_key = f"tmdb_tv_search_{title.lower()}"
        data = self._get("search/tv", {"query": title}, cache_key=cache_key)
        results = data.get("results", []) if data else []
        return results[0] if results else None

    def search_movie(self, title):
        cache_key = f"tmdb_movie_search_{title.lower()}"
        data = self._get("search/movie", {"query": title}, cache_key=cache_key)
        results = data.get("results", []) if data else []
        return results[0] if results else None

    def get_similar_shows(self, tmdb_id):
        cache_key = f"tmdb_tv_rec_{tmdb_id}"
        data = self._get(f"tv/{tmdb_id}/recommendations", cache_key=cache_key)
        return data.get("results", []) if data else []

    def get_similar_movies(self, tmdb_id):
        cache_key = f"tmdb_movie_rec_{tmdb_id}"
        data = self._get(f"movie/{tmdb_id}/recommendations", cache_key=cache_key)
        return data.get("results", []) if data else []

    def get_show_details(self, tmdb_id):
        cache_key = f"tmdb_tv_details_{tmdb_id}"
        params = {"append_to_response": "content_ratings,keywords,watch/providers"}
        return self._get(f"tv/{tmdb_id}", params=params, cache_key=cache_key)

    def get_movie_details(self, tmdb_id):
        cache_key = f"tmdb_movie_details_{tmdb_id}"
        params = {"append_to_response": "release_dates,keywords,watch/providers"}
        return self._get(f"movie/{tmdb_id}", params=params, cache_key=cache_key)

    def get_watch_providers(self, tmdb_id, is_movie=False):
        details = self.get_movie_details(tmdb_id) if is_movie else self.get_show_details(tmdb_id)
        if not details: return []
        
        results = details.get('watch/providers', {}).get('results', {}).get(self.region, {})
        flatrate = results.get('flatrate', [])
        return [p['provider_name'] for p in flatrate]

    def parse_advisory(self, details, is_movie=False):
        if not details: return "NR", "General"
        
        if is_movie:
            results = details.get('release_dates', {}).get('results', [])
            us_data = next((r for r in results if r['iso_3166_1'] == self.region), {})
            us_rating = us_data.get('release_dates', [{}])[0].get('certification', 'NR')
        else:
            ratings = details.get('content_ratings', {}).get('results', [])
            us_rating = next((r['rating'] for r in ratings if r['iso_3166_1'] == self.region), "NR")
        
        keywords_data = details.get('keywords', {})
        keywords = keywords_data.get('keywords' if is_movie else 'results', [])
            
        sensitive_tags = ['violence', 'nudity', 'sex', 'gore', 'profanity', 'drugs', 'dark']
        found_tags = [k['name'].capitalize() for k in keywords if k['name'].lower() in sensitive_tags]
        
        return us_rating, ", ".join(found_tags) if found_tags else "General"

    def get_genre_list(self, is_movie=False):
        m_type = "movie" if is_movie else "tv"
        cache_key = f"tmdb_genres_{m_type}"
        data = self._get(f"genre/{m_type}/list", cache_key=cache_key, ttl=86400) # Cache for 24h
        genres = data.get("genres", []) if data else []
        return {g['id']: g['name'] for g in genres}

    def get_cross_recommendations(self, tmdb_id, source_is_movie=True):
        details = self.get_movie_details(tmdb_id) if source_is_movie else self.get_show_details(tmdb_id)
        if not details: return []
        
        keywords_data = details.get('keywords', {})
        keywords = keywords_data.get('keywords' if source_is_movie else 'results', [])
        if not keywords: return []
        
        keyword_ids = "|".join([str(k['id']) for k in keywords[:3]])
        target_type = "movie" if not source_is_movie else "tv"
        cache_key = f"tmdb_cross_rec_{tmdb_id}_{target_type}"
        params = {
            "with_keywords": keyword_ids,
            "sort_by": "popularity.desc"
        }
        data = self._get(f"discover/{target_type}", params=params, cache_key=cache_key)
        return data.get("results", []) if data else []
