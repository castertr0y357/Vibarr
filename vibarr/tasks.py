# This file is kept for backward compatibility with string-based task references.
# All tasks have been moved to the vibarr/tasks/ package.
from .tasks.media.polling import poll_media_servers
from .tasks.discovery.recommendations import generate_recommendations
from .tasks.managers.sync import discover_universe_and_sync, sync_external_states
from .tasks.managers.actions import start_tasting, check_tasting_progress, trigger_auto_purge
