from django.views.generic import ListView, View
from django.shortcuts import redirect
from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from ..models import APIKey

class APIKeyListView(ListView):
    model = APIKey
    template_name: str = 'vibarr/partials/api_key_list.html'
    context_object_name: str = 'api_keys'

class CreateAPIKeyView(View):
    def post(self, request: HttpRequest) -> HttpResponse:
        name: str = request.POST.get('key_name', 'Unnamed Key')
        key: APIKey = APIKey.objects.create(name=name)
        messages.success(request, f"New API Key created: {key.name}")
        # If HTMX, return the partial list
        if request.headers.get('HX-Request'):
             return redirect('api_key_list')
        return redirect('settings')

class RevokeAPIKeyView(View):
    def post(self, request: HttpRequest, key_id: int) -> HttpResponse:
        try:
            key: APIKey = APIKey.objects.get(id=key_id)
            key.delete()
            messages.success(request, "API Key revoked.")
        except APIKey.DoesNotExist:
            messages.error(request, "Key not found.")
            
        if request.headers.get('HX-Request'):
             return redirect('api_key_list')
        return redirect('settings')
