from .models import AppConfig

def config_processor(request):
    """
    Makes the application configuration available in all templates.
    """
    return {
        'config': AppConfig.get_solo()
    }
