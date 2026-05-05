from django.views.generic import TemplateView, View
from django.shortcuts import render
from django.http import FileResponse
import os
import zipfile

class LogsView(TemplateView):
    template_name = 'vibarr/logs.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        log_file = os.path.join('logs', 'vibarr.log')
        lines = []
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                lines = f.readlines()[-200:]
        context['logs'] = lines
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
