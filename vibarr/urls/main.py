from django.urls import path
from ..views.dashboard import DashboardView, SyncStatusView
from ..views.search import VibeSearchView, VibeSearchActionView, TasteFromSearchView
from ..views.settings import SettingsView, UpdateSettingsView, GetLibrariesView, TestSettingsView, DiscoverPlexServersView, RefreshMetadataView, RevaluateRecommendationsView
from ..views.diagnostics import LogsView, DownloadLogsView
from ..views.setup import SetupWizardView, SetupActionView, PlexPinRequestView, PlexPinPollView, ResetSetupView, TestAutomationView
from ..views.nightcap import NightcapView, NightcapActionView
from ..views.api_keys import APIKeyListView, CreateAPIKeyView, RevokeAPIKeyView
from ..views.personas import SwitchPersonaView, CreatePersonaView
from ..views.history import HistoryView, BackfillHistoryView
from ..views.media_views import DiscoveryListView, TastingListView, CommittedListView
from ..views.universe import UniverseListView

urlpatterns = [
    path('universes/', UniverseListView.as_view(), name='universe_architect_list'),
    path('committed/', CommittedListView.as_view(), name='committed_list'),
    path('', DashboardView.as_view(), name='dashboard'),
    path('discoveries/', DiscoveryListView.as_view(), name='discoveries_list'),
    path('tastings/', TastingListView.as_view(), name='tastings_list'),
    path('history/', HistoryView.as_view(), name='history_view'),
    path('history/backfill/', BackfillHistoryView.as_view(), name='backfill_history'),
    path('sync-status/', SyncStatusView.as_view(), name='sync_status'),
    path('nightcap/', NightcapView.as_view(), name='nightcap'),
    path('nightcap/action/', NightcapActionView.as_view(), name='nightcap_action'),
    path('settings/libraries/', GetLibrariesView.as_view(), name='get_libraries'),
    path('setup/', SetupWizardView.as_view(), name='setup_wizard'),
    path('setup/action/', SetupActionView.as_view(), name='setup_action'),
    path('setup/plex/pin/', PlexPinRequestView.as_view(), name='plex_pin_request'),
    path('setup/plex/poll/<int:pin_id>/', PlexPinPollView.as_view(), name='plex_pin_poll'),
    path('setup/reset/', ResetSetupView.as_view(), name='setup_reset'),
    path('setup/test-automation/', TestAutomationView.as_view(), name='setup_test_automation'),
    path('search/', VibeSearchView.as_view(), name='vibe_search_page'),
    path('search/action/', VibeSearchActionView.as_view(), name='vibe_search'),
    path('search/taste/', TasteFromSearchView.as_view(), name='taste_from_search'),
    path('settings/', SettingsView.as_view(), name='settings'),
    path('settings/general/', SettingsView.as_view(), {'section': 'general'}, name='settings_general'),
    path('settings/servers/', SettingsView.as_view(), {'section': 'servers'}, name='settings_servers'),
    path('settings/automation/', SettingsView.as_view(), {'section': 'automation'}, name='settings_automation'),
    path('settings/intelligence/', SettingsView.as_view(), {'section': 'intelligence'}, name='settings_intelligence'),
    path('settings/governance/', SettingsView.as_view(), {'section': 'governance'}, name='settings_governance'),
    path('settings/household/', SettingsView.as_view(), {'section': 'household'}, name='settings_household'),
    path('settings/security/', SettingsView.as_view(), {'section': 'security'}, name='settings_security'),
    path('settings/update/', UpdateSettingsView.as_view(), name='update_settings'),
    path('settings/test/', TestSettingsView.as_view(), name='test_settings'),
    path('settings/plex/discover/', DiscoverPlexServersView.as_view(), name='discover_plex_servers'),
    path('settings/refresh-metadata/', RefreshMetadataView.as_view(), name='refresh_metadata'),
    path('settings/revaluate-recommendations/', RevaluateRecommendationsView.as_view(), name='revaluate_recommendations'),
    path('settings/keys/', APIKeyListView.as_view(), name='api_key_list'),
    path('settings/keys/create/', CreateAPIKeyView.as_view(), name='create_api_key'),
    path('settings/keys/revoke/<int:key_id>/', RevokeAPIKeyView.as_view(), name='revoke_api_key'),
    path('settings/personas/create/', CreatePersonaView.as_view(), name='create_persona'),
    path('personas/switch/<int:persona_id>/', SwitchPersonaView.as_view(), name='switch_persona'),
    path('logs/', LogsView.as_view(), name='logs_view'),
    path('logs/download/', DownloadLogsView.as_view(), name='download_logs'),
]
