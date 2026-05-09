import ipaddress
import logging
from django.shortcuts import redirect
from django.urls import reverse, resolve, Resolver404
from ..models import AppConfig, AuthMode

logger = logging.getLogger(__name__)

class VibarrAuthMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        config = AppConfig.get_solo()
        
        # 1. Bypass if auth is disabled
        if config.auth_mode == AuthMode.NONE:
            return self.get_response(request)
            
        # 2. Define allowed paths (login, static files, etc.)
        try:
            current_url_name = resolve(request.path_info).url_name
        except Resolver404:
            current_url_name = None

        allowed_url_names = ['login', 'health_check']
        
        # Check if the path is in the allowed list or starts with static/media
        if current_url_name in allowed_url_names or \
           request.path.startswith('/static/') or \
           request.path.startswith('/favicon.ico'):
            return self.get_response(request)

        # 3. Check Authentication Status
        is_authenticated = request.session.get('vibarr_auth', False)
        
        if config.auth_mode == AuthMode.ALWAYS:
            if not is_authenticated:
                return redirect('login')
                
        elif config.auth_mode == AuthMode.EXTERNAL:
            if not self.is_local_ip(request) and not is_authenticated:
                logger.info(f"Unauthorized external access attempt from {self.get_client_ip(request)}")
                return redirect('login')
                
        return self.get_response(request)

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    def is_local_ip(self, request):
        ip = self.get_client_ip(request)
        if not ip: return False
        
        # Strip port if present (IPv6 or misconfigured proxy)
        if ':' in ip and '.' in ip: # IPv4-mapped IPv6 or similar
             ip = ip.split(':')[-1]
        elif ']' in ip: # IPv6 with port [::1]:8000
             ip = ip.split(']')[0].replace('[', '')
             
        try:
            ip_obj = ipaddress.ip_address(ip)
            return ip_obj.is_private or ip_obj.is_loopback
        except ValueError:
            # If we can't parse it, assume it's external for safety
            return False
