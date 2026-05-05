from django.urls import path, include

urlpatterns = [
    path('', include('vibarr.urls.main')),
    path('auth/', include('vibarr.urls.auth')),
    path('api/', include('vibarr.urls.api')),
]
