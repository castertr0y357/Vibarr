from django.views.generic import ListView, View, CreateView
from django.shortcuts import redirect
from django.contrib import messages
from ..models import Persona, AppConfig

class SwitchPersonaView(View):
    def post(self, request, persona_id):
        config = AppConfig.get_solo()
        if persona_id == 0:
            config.active_persona = None
        else:
            try:
                persona = Persona.objects.get(id=persona_id)
                config.active_persona = persona
            except Persona.DoesNotExist:
                messages.error(request, "Persona not found.")
        
        config.save()
        if request.headers.get('HX-Request'):
             # Return just the toggle or redirect
             return redirect('dashboard')
        return redirect('dashboard')

class PersonaListView(ListView):
    model = Persona
    template_name = 'vibarr/partials/persona_list.html'
    context_object_name = 'personas'

class CreatePersonaView(View):
    def post(self, request):
        name = request.POST.get('name')
        rating = request.POST.get('max_content_rating', 'NR')
        ignored = request.POST.get('ignored_genres', '')
        
        Persona.objects.create(
            name=name,
            max_content_rating=rating,
            ignored_genres=ignored
        )
        messages.success(request, f"Persona '{name}' created.")
        return redirect('settings')
