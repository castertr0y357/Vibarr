from .base import AIBaseService
import json
import requests
import logging
import math

from ....models import Show, ShowState, MediaType, MediaWatchEvent
from ..tmdb_service import TMDBService
from ..heuristic_ranking import HeuristicRankingService

logger = logging.getLogger(__name__)

class AIRankingService(AIBaseService):
    def _determine_media_type(self, candidates):
        if not candidates:
            return MediaType.SHOW
        
        cand = candidates[0]
        if hasattr(cand, 'media_type'):
            return cand.media_type
        if isinstance(cand, dict):
            return cand.get('_media_type') or cand.get('media_type') or MediaType.SHOW
        return MediaType.SHOW

    def _build_two_bucket_profile(self, history_titles, media_type):
        """
        Builds the structured text for Core Taste Profile and Current Binge Vibe.
        """
        # 1. Format Core Taste Profile
        # Get Heuristic Profile for names and weights
        hrs = HeuristicRankingService()
        heuristic_profile = hrs._build_user_profile(media_type)
        
        # Sort genres and keywords by weight descending
        sorted_genres = sorted(
            heuristic_profile.get('genres', {}).items(),
            key=lambda x: x[1],
            reverse=True
        )
        sorted_keywords = sorted(
            heuristic_profile.get('keywords', {}).items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        genre_names = heuristic_profile.get('genre_names', {})
        keyword_names = heuristic_profile.get('keyword_names', {})
        
        # Format Top Genres (Top 5)
        top_genres_text = []
        for g_id, weight in sorted_genres[:5]:
            name = genre_names.get(g_id, f"Genre {g_id}")
            top_genres_text.append(f"{name} (Weight: {weight:.1f})")
            
        # Format Top Themes/Keywords (Top 8)
        top_keywords_text = []
        for k_id, weight in sorted_keywords[:8]:
            name = keyword_names.get(k_id, f"Theme {k_id}")
            top_keywords_text.append(f"{name} (Weight: {weight:.1f})")
            
        # Format Comfort Titles (items with play count >= 2, sorted by play count desc)
        comfort_titles = []
        recent_titles = []
        
        # If history_titles is a list of strings, convert to dict format
        history_list = []
        for item in history_titles:
            if isinstance(item, str):
                history_list.append({'title': item, 'play_count': 1})
            else:
                history_list.append(item)
                
        sorted_by_play = sorted(history_list, key=lambda x: x.get('play_count', 1), reverse=True)
        
        for item in sorted_by_play:
            title = item.get('title')
            play_count = item.get('play_count', 1)
            
            if play_count >= 5:
                comfort_titles.append(f"{title} ({play_count} views - Highly watched comfort title)")
            elif play_count >= 2:
                comfort_titles.append(f"{title} ({play_count} views - Frequently watched)")
            else:
                recent_titles.append(title)
                
        # 2. Format Current Binge Vibe (Last 5 unique watches from history_titles)
        # Since history_titles is originally ordered by latest watch descending, the first 5 in history_list represent the most recent unique watches.
        recent_watches_info = []
        tmdb = TMDBService()
        recent_5_titles = [item.get('title') for item in history_list[:5]]
        
        for title in recent_5_titles:
            event = MediaWatchEvent.objects.filter(show_title=title, tmdb_id__isnull=False).order_by('-watched_at').first()
            if event:
                details = tmdb.get_movie_details(event.tmdb_id) if media_type == MediaType.MOVIE else tmdb.get_show_details(event.tmdb_id)
                if details:
                    genres = ", ".join([g['name'] for g in details.get('genres', [])[:3]])
                    overview = details.get('overview', '')
                    if len(overview) > 150:
                        overview = overview[:147] + "..."
                    recent_watches_info.append(f"- {title} (Genres: {genres} - \"{overview}\")")
                else:
                    recent_watches_info.append(f"- {title}")
            else:
                recent_watches_info.append(f"- {title}")

        # Assemble output text
        lines = []
        lines.append("CORE TASTE PROFILE (Long-term favorites):")
        if top_genres_text:
            lines.append(f"  - Preferred Genres: {', '.join(top_genres_text)}")
        if top_keywords_text:
            lines.append(f"  - Preferred Themes/Vibes: {', '.join(top_keywords_text)}")
        if comfort_titles:
            lines.append("  - Comfort Titles & Favorites:")
            for t in comfort_titles[:10]:
                lines.append(f"    * {t}")
        
        lines.append("\nCURRENT BINGE VIBE (Last 5 unique watches):")
        if recent_watches_info:
            for info in recent_watches_info:
                lines.append(f"  {info}")
        else:
            lines.append("  None")
            
        return "\n".join(lines)

    def _format_rejected_shows(self):
        """
        Formats rejected shows with content rating and advisory keywords.
        """
        rejected = Show.objects.filter(state=ShowState.REJECTED).order_by('-updated_at')[:10]
        if not rejected.exists():
            return "  None"
            
        formatted = []
        for s in rejected:
            details = []
            if s.content_rating:
                details.append(s.content_rating)
            if s.content_advisory:
                details.append(s.content_advisory)
            
            if details:
                formatted.append(f"  - {s.title} ({' - '.join(details)})")
            else:
                formatted.append(f"  - {s.title}")
                
        return "\n".join(formatted)

    def rank_shows(self, history_titles, candidates, context=None):
        """Selects and ranks matches from candidates based on history."""
        media_type = self._determine_media_type(candidates)
        
        system_prompt = (
            "You are a specialized TV and Movie recommendation engine. "
            "You analyze user patterns (recurring actors, directors, specific vibes, content boundaries, and favorite comfort titles) and return results as a valid JSON array of objects. "
            "Each object MUST have: 'title', 'reasoning', and 'vibe_tags' (a list of 3-4 short keywords like 'Gritty', 'Slow-burn', 'Ensemble Cast')."
        )
        
        profile_formatted = self._build_two_bucket_profile(history_titles, media_type)
        rejected_formatted = self._format_rejected_shows()
        user_prompt = f"""
        User Taste Profile:
        {profile_formatted}
        
        Shows the user DISLIKED or REJECTED:
        {rejected_formatted}
        
        {f'CURRENT CONTEXT: It is {context}. Adapt suggestions to fit this time of day/week.' if context else ''}
        
        Candidates for recommendation:
        {json.dumps([{ 'title': c['title'], 'overview': c['overview'] } for c in candidates], indent=2)}
        
        Task: 
        Analyze why the user might have rejected certain shows based on their content ratings and advisories (e.g. if they rejected shows with TV-MA or Violence/Gore, avoid suggesting graphic content, but do not block the underlying genre if it aligns with their Core Taste Profile). Make intelligent, nuanced recommendations (e.g. if they rejected 'The Witcher' but love fantasy, recommend PG-13/TV-14 level fantasy like 'Rings of Power' rather than banning fantasy).
        
        Select exactly 5 matches for this user from the candidates list using a '3-1-1' strategy:
        1. SLOT 1, 2, and 3 (Recent Vibe Continuation): 3 high-confidence recommendations matching the genre, theme, and specific vibe of their Current Binge Vibe.
        2. SLOT 4 (Core Favorites / Comfort): 1 recommendation matching their long-term Core Taste Profile (highly-weighted genres/themes).
        3. SLOT 5 (Wildcard): 1 serendipitous, non-obvious connection.
        
        For each match, provide:
        1. The exact title from the candidates list.
        2. A 1-sentence 'reasoning' why it fits. 
        3. A numerical 'score' from 0.0 to 10.0 reflecting your confidence in the match.
        4. A list of 3-4 'vibe_tags'.
        
        CRITICAL: Return ONLY a raw JSON list.
        """
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.7,
            "chat_id": ""
        }
        if "localhost" in self.url or "11434" in self.url: payload["format"] = "json"

        try:
            response = requests.post(self.url, headers=self.headers, json=payload, timeout=120)
            response.raise_for_status()
            content = response.json().get('choices', [{}])[0].get('message', {}).get('content', '')
            data = self._parse_json_response(content, [])
            
            if isinstance(data, dict):
                return data.get('recommendations', [])
            return data if isinstance(data, list) else []
        except Exception as e:
            logger.error(f"AIRankingService.rank_shows error: {e}")
            return []

    def score_candidates(self, history_titles, candidates):
        """Scores ALL provided candidates based on history (no selection/filtering)."""
        media_type = self._determine_media_type(candidates)
        
        system_prompt = (
            "You are a specialized TV and Movie recommendation engine. "
            "You provide detailed scoring for a specific list of titles based on user history. "
            "Return results as a valid JSON object with a 'scores' key containing a list of objects."
        )
        
        profile_formatted = self._build_two_bucket_profile(history_titles, media_type)
        rejected_formatted = self._format_rejected_shows()
        user_prompt = f"""
        User Taste Profile:
        {profile_formatted}
        
        User REJECTED:
        {rejected_formatted}
        
        Evaluate the following {len(candidates)} candidates:
        {json.dumps([{ 'title': c['title'], 'overview': c['overview'] } for c in candidates], indent=2)}
        
        Task: 
        For EACH title in the list, evaluate its fit based on the user's taste profile. Score candidates higher if they align closely with the style, genre, or specific vibes of either their Current Binge Vibe or their long-term Core Taste Profile (highly-weighted genres/themes).
        Analyze why the user might have rejected certain shows based on their content ratings and advisories (e.g. if they rejected shows with TV-MA or Violence/Gore, avoid suggesting graphic content, but do not penalize the underlying genre if it aligns with their Core Taste Profile).
        
        Provide:
        1. 'title': Exact title from the list.
        2. 'score': Numerical score (0.0 to 10.0) reflecting match confidence.
        3. 'reasoning': 1-sentence explanation of the score.
        4. 'vibe_tags': 3-4 keywords.
        
        Return ONLY valid JSON in this format:
        {{
            "scores": [
                {{ "title": "...", "score": 8.5, "reasoning": "...", "vibe_tags": [...] }},
                ...
            ]
        }}
        """
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.3, # Lower temperature for more consistent scoring
            "chat_id": ""
        }
        if "localhost" in self.url or "11434" in self.url: payload["format"] = "json"

        try:
            response = requests.post(self.url, headers=self.headers, json=payload, timeout=180)
            response.raise_for_status()
            content = response.json().get('choices', [{}])[0].get('message', {}).get('content', '')
            data = self._parse_json_response(content, {})
            return data.get('scores', [])
        except Exception as e:
            logger.error(f"AIRankingService.score_candidates error: {e}")
            return []

    def get_mood_recommendations(self, history_titles, mood):
        """Suggests titles based on a specific 'Mood' and watch history."""
        profile_formatted = self._build_two_bucket_profile(history_titles, MediaType.SHOW)
        prompt = f"""
        User Taste Profile:
        {profile_formatted}
        
        The user is in the mood for: "{mood}"
        Suggest 5 Movies or TV Shows that fit this mood AND their past tastes.
        Pay special attention to their Current Binge Vibe and their long-term Core Taste Profile. Suggest titles that align with these profiles while fulfilling the requested mood.
        
        Return ONLY a JSON list of objects:
        [
            {{"title": "Title", "media_type": "MOVIE" or "SHOW", "reasoning": "Why it fits", "vibe_tags": ["Tag1", "Tag2"]}}
        ]
        """
        content = self._post(prompt, temperature=0.7, timeout=45, json_mode=True)
        data = self._parse_json_response(content, [])
        return data if isinstance(data, list) else data.get('recommendations', [])
