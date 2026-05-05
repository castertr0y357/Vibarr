import logging
from ...models import AppConfig

logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self):
        self.config = AppConfig.get_solo()

    def send_message(self, text, title=None):
        """Offloads notification sending to a background task."""
        from django_q.tasks import async_task
        try:
            async_task('vibarr.tasks.notifications.send_async_notification', text, title=title)
        except Exception as e:
            logger.error(f"Failed to queue notification: {e}")

    def notify_tasting_ready(self, show_title):
        self.send_message(
            f"🎬 Your tasting for <b>{show_title}</b> is now ready on your media server! Enjoy the first few episodes.",
            title="Tasting Ready"
        )

    def notify_universe_found(self, root_title, universe_name, count):
        self.send_message(
            f"🌌 New Universe Detected! Based on <b>{root_title}</b>, I have architected the <b>{universe_name}</b> collection with {count} titles.",
            title="Universe Architected"
        )

    def notify_purge(self, show_title, reason):
        self.send_message(
            f"🧹 <b>{show_title}</b> has been purged from your library. Reason: {reason}",
            title="Auto-Purge Executed"
        )
