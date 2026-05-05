import requests
import logging
from ...models import AppConfig

logger = logging.getLogger(__name__)

def send_async_notification(text, title=None):
    config = AppConfig.get_solo()
    
    # 1. Discord
    if config.discord_webhook_url:
        try:
            payload = {
                "embeds": [{
                    "title": title or "Vibarr Notification",
                    "description": text,
                    "color": 0xE94560
                }]
            }
            requests.post(config.discord_webhook_url, json=payload, timeout=10)
        except Exception as e:
            logger.error(f"Discord Notification Error: {e}")

    # 2. Telegram
    if config.telegram_bot_token and config.telegram_chat_id:
        try:
            url = f"https://api.telegram.org/bot{config.telegram_bot_token}/sendMessage"
            payload = {
                "chat_id": config.telegram_chat_id,
                "text": text,
                "parse_mode": "HTML"
            }
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            logger.error(f"Telegram Notification Error: {e}")
