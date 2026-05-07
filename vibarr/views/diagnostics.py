from django.views.generic import TemplateView, View
from django.shortcuts import render
from django.http import FileResponse
import os
import zipfile

class LogsView(TemplateView):
    template_name = 'vibarr/logs.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Logs
        log_file = os.path.join('logs', 'vibarr.log')
        lines = []
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                lines = f.readlines()[-200:]
        context['logs'] = lines
        
        # DB Stats
        from django.db import connection
        engine = connection.vendor
        size = "0.0 MB"
        
        try:
            if engine == 'postgresql':
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_database_size(current_database())")
                    size_bytes = cursor.fetchone()[0]
                    size = f"{size_bytes / (1024 * 1024):.1f} MB"
                engine_display = "PostgreSQL"
            elif engine == 'sqlite':
                db_path = connection.settings_dict['NAME']
                if os.path.exists(db_path):
                    size_bytes = os.path.getsize(db_path)
                    size = f"{size_bytes / (1024 * 1024):.1f} MB"
                engine_display = "SQLite"
            else:
                engine_display = engine.capitalize()
        except Exception:
            engine_display = "Unknown"
            size = "Error"
            
        context['db_engine'] = engine_display
        context['db_size'] = size
        
        return context

class DownloadLogsView(View):
    def get(self, request, *args, **kwargs):
        log_dir = 'logs'
        zip_path = os.path.join(log_dir, 'vibarr_logs.zip')
        
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for root, dirs, files in os.walk(log_dir):
                for file in files:
                    if file.endswith('.log'):
                        zipf.write(os.path.join(root, file), file)
        
        return FileResponse(open(zip_path, 'rb'), as_attachment=True, filename='vibarr_logs.zip')
