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

    def _repair_json(self, json_str):
        """
        Attempts to repair truncated or malformed JSON by:
        - Closing unclosed strings.
        - Matching mismatched braces/brackets.
        - Adding missing closing brackets/braces at the end.
        """
        clean_str = json_str.strip()
        if not clean_str:
            return ""
            
        result = []
        stack = []
        in_string = False
        escape = False
        
        i = 0
        while i < len(clean_str):
            char = clean_str[i]
            
            if in_string:
                if escape:
                    escape = False
                    result.append(char)
                elif char == '\\':
                    escape = True
                    result.append(char)
                elif char == '"':
                    in_string = False
                    result.append(char)
                else:
                    result.append(char)
            else:
                if char == '"':
                    in_string = True
                    result.append(char)
                elif char == '{':
                    stack.append('{')
                    result.append(char)
                elif char == '[':
                    stack.append('[')
                    result.append(char)
                elif char == '}':
                    while stack and stack[-1] == '[':
                        stack.pop()
                        result.append(']')
                    if stack and stack[-1] == '{':
                        stack.pop()
                        result.append(char)
                elif char == ']':
                    while stack and stack[-1] == '{':
                        stack.pop()
                        result.append('}')
                    if stack and stack[-1] == '[':
                        stack.pop()
                        result.append(char)
                else:
                    result.append(char)
            i += 1
            
        if escape:
            result.pop()
        
        if in_string:
            result.append('"')
            
        while stack:
            op = stack.pop()
            if op == '{':
                result.append('}')
            elif op == '[':
                result.append(']')
                
        return "".join(result)

    def _parse_json_response(self, content, default):
        """Helper to extract and parse JSON from AI response with self-healing capabilities."""
        if not content:
            return default
            
        json_str = None
        
        # 1. Try finding JSON inside code blocks first
        if "```" in content:
            parts = content.split("```")
            for part in parts:
                clean_part = part.strip()
                if not clean_part:
                    continue
                if clean_part.startswith("json"):
                    clean_part = clean_part[4:].strip()
                json_str = clean_part
                break

        if not json_str:
            # 2. Try finding JSON by looking for braces/brackets
            start_obj = content.find('{')
            start_arr = content.find('[')
            
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
            
        if not json_str:
            json_str = content.strip()

        # Try parsing directly
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass

        # Try repairing and parsing
        repaired = self._repair_json(json_str)
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            pass

        # Try truncating at the last '{' if it was a list of objects and we failed to parse
        try:
            last_brace = json_str.rfind('{')
            if last_brace != -1:
                truncated = json_str[:last_brace].strip()
                if truncated.endswith(','):
                    truncated = truncated[:-1].strip()
                
                if json_str.strip().startswith('['):
                    truncated += '\n]'
                elif json_str.strip().startswith('{'):
                    truncated += '\n}'
                    
                repaired_truncated = self._repair_json(truncated)
                return json.loads(repaired_truncated)
        except Exception as e:
            logger.warning(f"AI Integration - Warning - Truncation repair failed: {e}")

        logger.error(f"AI Integration - Error - JSON parse failed. Raw content (truncated): {content[:500]}")
        return default

    def _post(self, prompt, temperature=0.3, timeout=60, json_mode=False):
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "chat_id": ""
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
            logger.error(f"AI Integration - Error - API call failed: {e}")
            return None
