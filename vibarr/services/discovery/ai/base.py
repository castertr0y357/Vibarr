import requests
import json
import logging
from ....models import AppConfig

logger = logging.getLogger(__name__)

class AIBaseService:
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

    def _parse_json_response(self, content, default):
        """Helper to extract and parse JSON from AI response."""
        try:
            if not content:
                return default
            
            # Extract from code blocks if present
            if "```" in content:
                # Try to find JSON block
                parts = content.split("```")
                for part in parts:
                    clean_part = part.strip()
                    if clean_part.startswith("json"):
                        clean_part = clean_part[4:].strip()
                    try:
                        return json.loads(clean_part)
                    except json.JSONDecodeError:
                        continue
            
            # Try parsing the whole thing
            return json.loads(content.strip())
        except Exception as e:
            logger.error(f"AI JSON Parse Error: {e}. Raw content (truncated): {content[:200]}")
            return default

    def _post(self, prompt, temperature=0.3, timeout=30, json_mode=False):
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
            response = requests.post(self.url, headers=self.headers, json=payload, timeout=timeout)
            response.raise_for_status()
            return response.json().get('choices', [{}])[0].get('message', {}).get('content', '')
        except Exception as e:
            logger.error(f"AI API Error: {e}")
            return None
