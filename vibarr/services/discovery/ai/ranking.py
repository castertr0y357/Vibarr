from .base import AIBaseService
import json

class AIRankingService(AIBaseService):
    def rank_shows(self, history_titles, candidates, context=None):
        """Selects and ranks matches from candidates based on history."""
        from ....models import Show, ShowState
        rejected_shows = Show.objects.filter(state=ShowState.REJECTED).values_list('title', flat=True)[:10]
        
        system_prompt = (
            "You are a specialized TV and Movie recommendation engine. "
            "You analyze user patterns (recurring actors, directors, specific vibes) and return results as a valid JSON array of objects. "
            "Each object MUST have: 'title', 'reasoning', and 'vibe_tags' (a list of 3-4 short keywords like 'Gritty', 'Slow-burn', 'Ensemble Cast')."
        )
        
        user_prompt = f"""
        User Watch History (Liked): {', '.join(history_titles)}
        Shows the user DISLIKED or REJECTED: {', '.join(rejected_shows)}
        
        {f'CURRENT CONTEXT: It is {context}. Adapt suggestions to fit this time of day/week.' if context else ''}

        Candidates for recommendation:
        {json.dumps([{ 'title': c['title'], 'overview': c['overview'] } for c in candidates], indent=2)}
        
        Task: 
        Select exactly 5 matches for this user from the candidates list using a '4+1 Serendipity' strategy:
        1. TOP 4 MATCHES: High-confidence matches based on similar genres, recurring actors, or direct stylistic sequels.
        2. ONE WILDCARD: A non-obvious connection. Find a title that might be in a completely different genre but shares a deep 'Thematic DNA' or 'Vibe' with their history. 

        For each match, provide:
        1. The exact title from the candidates list.
        2. A 1-sentence 'reasoning' why it fits. 
        3. A numerical 'score' from 0.0 to 10.0 reflecting your confidence in the match.
        4. A list of 3-4 'vibe_tags'.
        
        CRITICAL: Return ONLY a raw JSON list.
        """
        
        # We need to pass system prompt too, so we'll customize _post or just do it here
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.7
        }
        if "localhost" in self.url or "11434" in self.url: payload["format"] = "json"

        try:
            import requests
            response = requests.post(self.url, headers=self.headers, json=payload, timeout=60)
            response.raise_for_status()
            content = response.json().get('choices', [{}])[0].get('message', {}).get('content', '')
            data = self._parse_json_response(content, [])
            
            if isinstance(data, dict):
                return data.get('recommendations', [])
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def get_mood_recommendations(self, history_titles, mood):
        """Suggests titles based on a specific 'Mood' and watch history."""
        prompt = f"""
        User Watch History: {', '.join(history_titles)}
        The user is in the mood for: "{mood}"
        Suggest 5 Movies or TV Shows that fit this mood AND their past tastes.
        
        Return ONLY a JSON list of objects:
        [
            {{"title": "Title", "media_type": "MOVIE" or "SHOW", "reasoning": "Why it fits", "vibe_tags": ["Tag1", "Tag2"]}}
        ]
        """
        content = self._post(prompt, temperature=0.7, timeout=45, json_mode=True)
        data = self._parse_json_response(content, [])
        return data if isinstance(data, list) else data.get('recommendations', [])
