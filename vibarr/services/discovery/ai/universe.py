from .base import AIBaseService

class AIUniverseService(AIBaseService):
    def identify_universe(self, title):
        """Identifies if a title belongs to a larger cinematic universe."""
        prompt = f"""
        Does the movie or show "{title}" belong to a larger 'Cinematic Universe' or multi-franchise continuity?
        (Examples: MCU, Star Wars, DCU, MonsterVerse, Spider-Verse including legacy films, etc.)
        
        If YES, return a JSON object with:
        - "universe_name": The definitive name for the collection (e.g. "Marvel Cinematic Universe")
        - "members": A list of all core Movies and Shows in that universe in release order, with their release year in parentheses (e.g. "Iron Man (2008)", "WandaVision (2021)", "Thor: Love and Thunder (2022)").
        
        If NO, return: {{"universe_name": null, "members": []}}
        
        CRITICAL RULES:
        1. Only include canonical, officially produced movies and shows that are actual entries of the cinematic universe.
        2. Strictly exclude fan-made films, unofficial bootlegs, mockbusters, documentaries, or unrelated titles that simply share similar wording.
        3. Do not include titles that sound similar but are not part of the official universe continuity.
        
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
