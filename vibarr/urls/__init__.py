from django.urls import path, include
from . import main, auth, api

urlpatterns = [
    path('', include(main)),
    path('auth/', include(auth)),
    path('api/', include(api)),
]
