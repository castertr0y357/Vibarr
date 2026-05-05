from django.urls import path
from ..views.auth import StartPlexAuthView, FinishPlexAuthView

urlpatterns = [
    path('plex/start/', StartPlexAuthView.as_view(), name='start_plex_auth'),
    path('plex/finish/', FinishPlexAuthView.as_view(), name='finish_plex_auth'),
]
