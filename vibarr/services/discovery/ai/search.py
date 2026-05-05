from .base import AIBaseService

class AISearchService(AIBaseService):
    def vibe_search(self, query):
        """Uses AI to suggest titles that match a natural language query."""
        prompt = f"""
        User is looking for something to watch with this 'vibe': "{query}"
        Suggest 10-15 Movies and TV Shows that perfectly capture this atmospheric or thematic description.
        
        Return ONLY a JSON object:
        {{
            "recommendations": [
                {{"title": "Title", "media_type": "MOVIE" or "SHOW", "reasoning": "Brief explanation"}}
            ]
        }}
        """
        content = self._post(prompt, temperature=0.7, timeout=45, json_mode=True)
        data = self._parse_json_response(content, {"recommendations": []})
        return data.get('recommendations', [])

    def get_simple_narrative(self, prompt):
        """Generates a simple text response from the AI."""
        return self._post(prompt, temperature=0.7, timeout=30)
