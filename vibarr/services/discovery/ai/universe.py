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

    def analyze_universe_ecosystem(self, universes):
        """Analyzes current universes and suggests merges for alignment."""
        import json
        prompt = f"""
        You are the Cinematic Universe Architect. You are analyzing a list of user-defined 'Cinematic Universes' to find potential fragmentation, overlaps, and redundancy, and recommend merges to align them.
        
        Here are the current universes and their titles:
        {json.dumps(universes, indent=2)}
        
        Identify which universes should be merged/combined.
        (e.g., if there is a 'Sony's Spider-Man Universe' and a 'Marvel Cinematic Universe', or separate entries for sequels/spin-offs like 'Star Wars' and 'The Mandalorian' that should be consolidated).
        
        Rules:
        1. Only suggest a merge if there is a strong canonical or narrative continuity link between them.
        2. A merge suggestion MUST specify the "source_universe" (the name of the universe to be merged) and the "target_universe" (the name of the universe to merge it into). Both MUST be exact names from the list provided above.
        3. Do not suggest merging unrelated universes (e.g. do not merge Marvel and Star Wars).
        4. For each suggestion, provide a "confidence" score (integer 1-10) and a clear "reasoning" text explaining the crossover/link.
        
        Return a JSON list of objects:
        [
          {{
            "source_universe": "Name of Source",
            "target_universe": "Name of Target",
            "confidence": 8,
            "reasoning": "Detailed explanation..."
          }}
        ]
        
        If no merges are recommended, return an empty list: [].
        Return ONLY valid JSON.
        """
        content = self._post(prompt, temperature=0.3, json_mode=True)
        return self._parse_json_response(content, [])

