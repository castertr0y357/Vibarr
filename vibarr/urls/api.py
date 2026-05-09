from django.urls import path
from ..views.actions import HealthCheckView, TasteShowView, RejectShowView, TogglePinShowView, StopAndDeleteShowView, ManualSyncView, UniverseSyncView, MarkWatchedView, ResetSyncStatusView, ExternalSyncView
from ..views.universe import CompleteUniverseView
from ..views import webhooks

urlpatterns = [
    # Health Checks
    path('test/sonarr/', HealthCheckView.as_view(), {'service_type': 'sonarr'}, name='test_sonarr'),
    path('test/radarr/', HealthCheckView.as_view(), {'service_type': 'radarr'}, name='test_radarr'),
    path('test/media/', HealthCheckView.as_view(), {'service_type': 'media'}, name='test_media_health'),
    path('test/jellyfin/', HealthCheckView.as_view(), {'service_type': 'jellyfin'}, name='test_jellyfin'),
    path('test/ai/', HealthCheckView.as_view(), {'service_type': 'ai'}, name='test_ai'),
    
    # Webhooks
    path('webhooks/plex/', webhooks.PlexWebhookView.as_view(), name='plex_webhook'),
    path('webhooks/jellyfin/', webhooks.JellyfinWebhookView.as_view(), name='jellyfin_webhook'),
    
    # Actions
    path('show/<int:show_id>/taste/', TasteShowView.as_view(), name='taste_show'),
    path('show/<int:show_id>/reject/', RejectShowView.as_view(), name='reject_show'),
    path('show/<int:show_id>/pin/', TogglePinShowView.as_view(), name='toggle_pin'),
    path('show/<int:show_id>/delete/', StopAndDeleteShowView.as_view(), name='stop_and_delete'),
    path('show/<int:show_id>/watched/', MarkWatchedView.as_view(), name='mark_watched'),
    path('sync/manual/', ManualSyncView.as_view(), name='manual_sync'),
    path('sync/reset/', ResetSyncStatusView.as_view(), name='reset_sync'),
    path('sync/universe/', UniverseSyncView.as_view(), name='universe_sync'),
    path('sync/external/', ExternalSyncView.as_view(), name='external_sync'),
    path('universe/complete/', CompleteUniverseView.as_view(), name='complete_universe'),
]
