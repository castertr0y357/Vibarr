from django.views.generic import TemplateView
from django.views import View
from django.http import HttpResponse
from .mixins import ConfigMixin
import requests
import logging

logger = logging.getLogger(__name__)

CURRENT_VERSION = '0.5.0-BETA'

class AboutView(ConfigMixin, TemplateView):
    template_name = 'vibarr/about.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['version'] = CURRENT_VERSION
        return context

class CheckUpdateView(View):
    def post(self, request):
        headers = {
            'User-Agent': 'Vibarr-App'
        }
        try:
            # Query the latest release tag from GitHub API
            response = requests.get(
                'https://api.github.com/repos/castertr0y357/Vibarr/releases/latest', 
                headers=headers, 
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                latest_tag = data.get('tag_name', '').strip()
                
                # Normalize tags (e.g. stripping 'v' prefix if present)
                clean_latest = latest_tag.lstrip('v')
                clean_current = CURRENT_VERSION.lstrip('v')
                
                if clean_latest == clean_current:
                    html = """
                    <div id="update-check-container" class="mt-2">
                        <span class="text-[10px] text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-full px-4 py-1.5 flex items-center gap-1.5">
                            <svg class="w-3 h-3 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
                            You are running the latest version!
                        </span>
                    </div>
                    """
                else:
                    html = f"""
                    <div id="update-check-container" class="mt-2">
                        <a href="https://github.com/castertr0y357/Vibarr/releases/latest" target="_blank"
                           class="text-[10px] text-amber-400 bg-amber-500/10 border border-amber-500/20 rounded-full px-4 py-1.5 flex items-center gap-1.5 hover:bg-amber-500/20 transition-all duration-300">
                            <span class="relative flex h-2 w-2">
                              <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
                              <span class="relative inline-flex rounded-full h-2 w-2 bg-amber-500"></span>
                            </span>
                            Update Available: {latest_tag} (Get Update)
                        </a>
                    </div>
                    """
                return HttpResponse(html)
            else:
                logger.warning(f"About - Warning - GitHub update check returned {response.status_code}")
        except Exception as e:
            logger.error(f"About - Error - Update check failed: {e}")
            
        # Error fallback
        error_html = """
        <div id="update-check-container" class="mt-2 flex flex-col items-center gap-1.5">
            <span class="text-[10px] text-rose-400 bg-rose-500/10 border border-rose-500/20 rounded-full px-4 py-1 flex items-center gap-1.5">
                Failed to check for updates
            </span>
            <button type="button" 
                    hx-post="/about/check-update/" 
                    hx-target="#update-check-container"
                    hx-swap="outerHTML"
                    class="text-[9px] text-gray-500 hover:text-gray-300 underline transition">
                Retry
            </button>
        </div>
        """
        return HttpResponse(error_html)
