from django.views.generic import ListView, View
from django.shortcuts import redirect, render
from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.utils import timezone
from ..models import APIKey

class APIKeyListView(ListView):
    model = APIKey
    template_name: str = 'vibarr/partials/api_key_list.html'
    context_object_name: str = 'api_keys'

    def get_queryset(self):
        return APIKey.objects.filter(deleted_at__isnull=True).order_by('-created_at')

class CreateAPIKeyView(View):
    def post(self, request: HttpRequest) -> HttpResponse:
        name: str = request.POST.get('key_name', '').strip()
        if not name:
            name = 'Unnamed Key'
            
        key_obj, raw_key = APIKey.create_key(name=name)
        messages.success(request, f"New API Key created: {key_obj.name}")
        
        # If HTMX, render the list partial directly with the new raw key
        if request.headers.get('HX-Request'):
            api_keys = APIKey.objects.filter(deleted_at__isnull=True).order_by('-created_at')
            return render(request, 'vibarr/partials/api_key_list.html', {
                'api_keys': api_keys,
                'new_raw_key': raw_key,
                'new_key_id': key_obj.id,
            })
            
        # If standard POST, store the raw key in session for a one-time display on redirect
        request.session['new_raw_key'] = raw_key
        request.session['new_key_id'] = key_obj.id
        return redirect('settings_security')

class RevokeAPIKeyView(View):
    def post(self, request: HttpRequest, key_id: int) -> HttpResponse:
        try:
            key: APIKey = APIKey.objects.get(id=key_id, deleted_at__isnull=True)
            key.deleted_at = timezone.now()
            key.is_active = False
            key.save()
            messages.success(request, "API Key revoked.")
        except APIKey.DoesNotExist:
            messages.error(request, "Key not found.")
            
        if request.headers.get('HX-Request'):
             return redirect('api_key_list')
        return redirect('settings_security')
