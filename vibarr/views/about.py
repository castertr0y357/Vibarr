from django.views.generic import TemplateView
from .mixins import ConfigMixin

class AboutView(ConfigMixin, TemplateView):
    template_name = 'vibarr/about.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['version'] = '0.5.0-BETA'  # Example version
        return context
