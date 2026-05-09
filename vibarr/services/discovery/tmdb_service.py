from ...models import AppConfig
import requests
from django.conf import settings
from django.core.cache import cache
import logging
import time
import re

logger = logging.getLogger(__name__)

class TMDBService:
    BASE_URL = "https://api.themoviedb.org/3"
    _session = None
    
    def __init__(self, api_key=None):
        config = AppConfig.get_solo()
        self.api_key = api_key or config.tmdb_api_key or getattr(settings, 'TMDB_API_KEY', '')
        self.region = config.tmdb_region or "US"
        self.language = config.tmdb_language or "en-US"
        
        if TMDBService._session is None:
            TMDBService._session = requests.Session()

    def test_connection(self):
        if not self.api_key: return False
        try:
            url = f"{self.BASE_URL}/configuration"
            params = {"api_key": self.api_key}
            response = self._session.get(url, params=params, timeout=5)
            return response.status_code == 200
        except Exception:
            return False

    def _get(self, endpoint, params=None, cache_key=None, ttl=3600):
        if cache_key:
            # Sanitize cache key for backends like memcached
            cache_key = cache_key.replace(':', '_').replace(' ', '_').replace('(', '').replace(')', '')
            cached = cache.get(cache_key)
            if cached: return cached

        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        final_params = {"api_key": self.api_key}
        if params: final_params.update(params)
        
        logger.debug(f"TMDB Request: {endpoint} (params: {params})")
        
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                response = self._session.get(url, params=final_params, timeout=10)
                
                # If we get a 50x error, retry after a short delay
                if response.status_code in [502, 503, 504] and attempt < max_retries:
                    time.sleep(1)
                    continue
                    
                response.raise_for_status()
                data = response.json()
                if cache_key: cache.set(cache_key, data, ttl)
                return data
            except Exception as e:
                status_code = getattr(e, 'response', None)
                if status_code:
                    status_code = status_code.status_code
                
                if attempt == max_retries:
                    logger.error(f"TMDB Final Error [{endpoint}] after {max_retries} retries. Status: {status_code}. Error: {e}")
                    return None
                
                wait = (attempt + 1) * 2
                logger.warning(f"TMDB Retry {attempt+1}/{max_retries} for [{endpoint}] due to: {e}. Waiting {wait}s...")
                time.sleep(wait)
        return None

    def search_show(self, title):
        year = None
        clean_title = title
        match = re.search(r'\((?:.*?)((?:19|20)\d{2})(?:.*?)\)', title)
        if match:
            year = match.group(1)
            clean_title = title.replace(match.group(0), '').strip()

        cache_key = f"tmdb_tv_search_{clean_title.lower()}_{year}"
        params = {"query": clean_title}
        if year: params["first_air_date_year"] = year
        
        data = self._get("search/tv", params, cache_key=cache_key)
        results = data.get("results", []) if data else []
        return results[0] if results else None

    def search_movie(self, title):
        year = None
        clean_title = title
        match = re.search(r'\((?:.*?)((?:19|20)\d{2})(?:.*?)\)', title)
        if match:
            year = match.group(1)
            clean_title = title.replace(match.group(0), '').strip()

        cache_key = f"tmdb_movie_search_{clean_title.lower()}_{year}"
        params = {"query": clean_title}
        if year: params["year"] = year

        data = self._get("search/movie", params, cache_key=cache_key)
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
        params = {"append_to_response": "content_ratings,keywords,watch/providers,external_ids"}
        return self._get(f"tv/{tmdb_id}", params=params, cache_key=cache_key)

    def get_movie_details(self, tmdb_id):
        cache_key = f"tmdb_movie_details_{tmdb_id}"
        params = {"append_to_response": "release_dates,keywords,watch/providers,external_ids"}
        return self._get(f"movie/{tmdb_id}", params=params, cache_key=cache_key)

    def get_collection(self, collection_id):
        cache_key = f"tmdb_collection_{collection_id}"
        return self._get(f"collection/{collection_id}", cache_key=cache_key)

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
