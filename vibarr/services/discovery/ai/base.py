import requests
import json
import logging
from ....models import AppConfig

logger = logging.getLogger(__name__)

class AIBaseService:
    _session = None

    def __init__(self, config=None):
        if not config:
            config = AppConfig.get_solo()
        self.url = config.ai_api_url
        self.model = config.ai_model
        self.api_key = config.ai_api_key
        
        self.headers = {
            "Content-Type": "application/json"
        }
        if self.api_key:
            self.headers["Authorization"] = f"Bearer {self.api_key}"
            
        if AIBaseService._session is None:
            AIBaseService._session = requests.Session()

    def _parse_json_response(self, content, default):
        """Helper to extract and parse JSON from AI response."""
        if not content:
            return default
            
        # 1. Try finding JSON inside code blocks first
        if "```" in content:
            parts = content.split("```")
            for part in parts:
                clean_part = part.strip()
                if not clean_part:
                    continue
                
                # Strip language identifiers like 'json' or 'json_object'
                if clean_part.startswith("json"):
                    clean_part = clean_part[4:].strip()
                
                try:
                    return json.loads(clean_part)
                except json.JSONDecodeError:
                    continue

        # 2. Try finding JSON by looking for braces/brackets if not already found in blocks
        try:
            # Find the first { or [ and last } or ]
            start_obj = content.find('{')
            start_arr = content.find('[')
            
            # Determine which comes first
            start = -1
            if start_obj != -1 and start_arr != -1:
                start = min(start_obj, start_arr)
            elif start_obj != -1:
                start = start_obj
            elif start_arr != -1:
                start = start_arr
                
            if start != -1:
                end_obj = content.rfind('}')
                end_arr = content.rfind(']')
                end = max(end_obj, end_arr)
                
                if end != -1 and end > start:
                    json_str = content[start:end+1]
                    try:
                        return json.loads(json_str)
                    except json.JSONDecodeError:
                        pass # Fall through to whole thing
            
            # 3. Fallback: Try parsing the whole thing (if no braces found or extraction failed)
            return json.loads(content.strip())
        except Exception as e:
            # Only log if we couldn't find ANY valid JSON
            logger.error(f"AI JSON Parse Error: {e}. Raw content (truncated): {content[:500]}")
            return default

    def _post(self, prompt, temperature=0.3, timeout=60, json_mode=False):
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature
        }
        
        if json_mode:
            if "gpt-" in self.model.lower():
                payload["response_format"] = { "type": "json_object" }
            if "localhost" in self.url or "11434" in self.url:
                payload["format"] = "json"

        try:
            response = self._session.post(self.url, headers=self.headers, json=payload, timeout=timeout)
            response.raise_for_status()
            return response.json().get('choices', [{}])[0].get('message', {}).get('content', '')
        except Exception as e:
            logger.error(f"AI API Error: {e}")
            return None
