from django.views.generic import ListView, View
from ..models import MediaWatchEvent, AppConfig
from django.shortcuts import redirect
from django.contrib import messages
from ..tasks.media.polling import poll_media_servers
from django_q.tasks import async_task

class HistoryView(ListView):
    model = MediaWatchEvent
    template_name = 'vibarr/history.html'
    context_object_name = 'events'
    paginate_by = 50

    def get_queryset(self):
        from django.db.models import Max, Count, F
        return MediaWatchEvent.objects.values(
            'show_title', 'media_type', 'source_server', 'tmdb_id'
        ).annotate(
            watched_at=Max('watched_at'),
            event_count=Count('id'),
            poster_path=F('show__poster_path')
        ).order_by('-watched_at')

    def get_template_names(self):
        if self.request.GET.get('partial') == 'true':
            return ['vibarr/partials/history_list.html']
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['config'] = AppConfig.get_solo()
        
        paginator = context.get('paginator')
        page_obj = context.get('page_obj')
        if paginator and page_obj:
            context['page_range'] = paginator.get_elided_page_range(page_obj.number, on_each_side=2, on_ends=1)
            
        return context

class BackfillHistoryView(View):
    def post(self, request):
        # Poll for the last 10 years (effectively full history)
        async_task(poll_media_servers, hours=87600)
        messages.success(request, "Full history backfill triggered. This may take a few minutes.")
        return redirect('history_view')
