from django.urls import path
from ..views.dashboard import DashboardView, SyncStatusView
from ..views.search import VibeSearchView, VibeSearchActionView, TasteFromSearchView
from ..views.settings import SettingsView, UpdateSettingsView, GetLibrariesView, TestSettingsView
from ..views.diagnostics import LogsView, DownloadLogsView
from ..views.setup import SetupWizardView, SetupActionView, PlexPinRequestView, PlexPinPollView, ResetSetupView, TestAutomationView
from ..views.nightcap import NightcapView, NightcapActionView

from ..views.api_keys import APIKeyListView, CreateAPIKeyView, RevokeAPIKeyView
from ..views.personas import SwitchPersonaView, CreatePersonaView

urlpatterns = [
    path('', DashboardView.as_view(), name='dashboard'),
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
    path('settings/update/', UpdateSettingsView.as_view(), name='update_settings'),
    path('settings/test/', TestSettingsView.as_view(), name='test_settings'),
    path('settings/keys/', APIKeyListView.as_view(), name='api_key_list'),
    path('settings/keys/create/', CreateAPIKeyView.as_view(), name='create_api_key'),
    path('settings/keys/revoke/<int:key_id>/', RevokeAPIKeyView.as_view(), name='revoke_api_key'),
    path('settings/personas/create/', CreatePersonaView.as_view(), name='create_persona'),
    path('personas/switch/<int:persona_id>/', SwitchPersonaView.as_view(), name='switch_persona'),
    path('logs/', LogsView.as_view(), name='logs_view'),
    path('logs/download/', DownloadLogsView.as_view(), name='download_logs'),
]
