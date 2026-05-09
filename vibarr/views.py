# This file is kept for backward compatibility with string-based view references.
# All views have been moved to the vibarr/views/ package as Class-Based Views.
from .views.dashboard import DashboardView
from .views.settings import SettingsView, UpdateSettingsView
from .views.search import VibeSearchView, VibeSearchActionView, TasteFromSearchView
from .views.actions import RejectShowView, TasteShowView, ManualSyncView, UniverseSyncView, HealthCheckView, StopAndDeleteShowView
from .views.auth import StartPlexAuthView, FinishPlexAuthView
from .views.diagnostics import LogsView, DownloadLogsView
from .views.media_views import DiscoveryListView, TastingListView, CommittedListView
