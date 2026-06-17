from django.views.generic import TemplateView, View
from django.shortcuts import render
from django.http import FileResponse
import os
import zipfile
import io
from django.db import connection
import logging

logger = logging.getLogger(__name__)

class LogsView(TemplateView):
    template_name = 'vibarr/logs.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Logs
        log_file = os.path.join('logs', 'vibarr.log')
        lines = []
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r') as f:
                    lines = f.readlines()[-200:]
            except (PermissionError, OSError):
                lines = ["[Permission denied or error reading log file]"]
        context['logs'] = lines
        
        # DB Stats
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
        except Exception as e:
            logger.error(f"Diagnostics - Error - Could not determine DB size: {e}")
            engine_display = "Unknown"
            size = "Error"
            
        context['db_engine'] = engine_display
        context['db_size'] = size
        
        return context

class DownloadLogsView(View):
    def get(self, request, *args, **kwargs):
        log_dir = 'logs'
        
        # Build the zip in memory to avoid write permission errors on the filesystem
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
            if os.path.exists(log_dir):
                for root, dirs, files in os.walk(log_dir):
                    for file in files:
                        if file.endswith('.log'):
                            file_path = os.path.join(root, file)
                            try:
                                zipf.write(file_path, file)
                            except (PermissionError, OSError):
                                pass
        
        zip_buffer.seek(0)
        return FileResponse(zip_buffer, as_attachment=True, filename='vibarr_logs.zip')


def handler500(request, *args, **kwargs):
    """
    Custom 500 error handler that displays a user-friendly error page with the correlation ID.
    """
    from ..middleware.correlation import get_correlation_id
    correlation_id = get_correlation_id()
    # Log the failure with correlation id
    logger.error(f"Server Error - Error - Internal Server Error (500) occurred. Correlation ID: {correlation_id}")
    return render(request, 'vibarr/500.html', {'correlation_id': correlation_id}, status=500)
