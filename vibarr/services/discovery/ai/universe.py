from .base import AIBaseService

class AIUniverseService(AIBaseService):
    def identify_universe(self, title):
        """Identifies if a title belongs to a larger cinematic universe."""
        prompt = f"""
        Does the movie or show "{title}" belong to a larger 'Cinematic Universe' or multi-franchise continuity?
        (Examples: MCU, Star Wars, DCU, MonsterVerse, Spider-Verse including legacy films, etc.)
        
        If YES, return a JSON object with:
        - "universe_name": The definitive name for the collection (e.g. "Marvel Cinematic Universe")
        - "members": A list of all core Movies and Shows in that universe in release order.
        
        If NO, return: {{"universe_name": null, "members": []}}
        
        Return ONLY valid JSON.
        """
        content = self._post(prompt, temperature=0.3, json_mode=True)
        return self._parse_json_response(content, {"universe_name": None, "members": []})

    def identify_cross_media_bridge(self, title, media_type):
        """Identifies if a Movie has a TV sibling or vice versa."""
        other_type = "TV Show" if media_type == "MOVIE" else "Movie"
        prompt = f"""
        The user just finished the {media_type}: "{title}".
        Is there a direct counterpart in the {other_type} format?
        (e.g. Movie based on the show, Show based on the movie, or shared continuity).
        
        If YES, return a JSON object with:
        - "title": The title of the counterpart.
        - "media_type": "MOVIE" or "SHOW".
        - "reasoning": Why they should watch this next (e.g. "Direct sequel series", "The original film that inspired the show").
        
        If NO, return: {{"title": null}}
        
        Return ONLY raw JSON.
        """
        content = self._post(prompt, temperature=0.3, json_mode=True)
        return self._parse_json_response(content, {"title": None})
