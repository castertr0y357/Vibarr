from django.views.generic import ListView, View
from django.shortcuts import redirect
from django.contrib import messages
from django.http import JsonResponse
from ..models import APIKey

class APIKeyListView(ListView):
    model = APIKey
    template_name = 'vibarr/partials/api_key_list.html'
    context_object_name = 'api_keys'

class CreateAPIKeyView(View):
    def post(self, request):
        name = request.POST.get('key_name', 'Unnamed Key')
        key = APIKey.objects.create(name=name)
        messages.success(request, f"New API Key created: {key.name}")
        # If HTMX, return the partial list
        if request.headers.get('HX-Request'):
             return redirect('api_key_list')
        return redirect('settings')

class RevokeAPIKeyView(View):
    def post(self, request, key_id):
        try:
            key = APIKey.objects.get(id=key_id)
            key.delete()
            messages.success(request, "API Key revoked.")
        except APIKey.DoesNotExist:
            messages.error(request, "Key not found.")
            
        if request.headers.get('HX-Request'):
             return redirect('api_key_list')
        return redirect('settings')
