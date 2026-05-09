from django.core.management.base import BaseCommand
from django_q.models import Schedule
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Initializes the default schedules for Vibarr background tasks'

    def handle(self, *args, **options):
        # Define the desired schedules
        # Note: We use the full python path for 'func'
        schedules = [
            {
                'name': 'Library & History Polling',
                'func': 'vibarr.tasks.media.polling.poll_media_servers',
                'schedule_type': Schedule.MINUTES,
                'minutes': 15,
                'kwargs': {'hours': 2}
            },
            {
                'name': 'Autonomous Scout (AI Discovery)',
                'func': 'vibarr.tasks.discovery.scouts.background_scout',
                'schedule_type': Schedule.HOURLY
            },
            {
                'name': 'Universe Architect Sync (Franchise Discovery)',
                'func': 'vibarr.tasks.managers.sync.batch_universe_sync',
                'schedule_type': Schedule.DAILY
            },
            {
                'name': 'Discovery Backlog Refresher',
                'func': 'vibarr.tasks.discovery.recommendations.refresh_discovery_tracks',
                'schedule_type': Schedule.HOURLY
            },
            {
                'name': 'Metadata Maintenance (Ratings & IDs)',
                'func': 'vibarr.tasks.discovery.recommendations.refresh_metadata_backlog',
                'schedule_type': Schedule.DAILY
            },
            {
                'name': 'External State Sync (Sonarr/Radarr Alignment)',
                'func': 'vibarr.tasks.managers.sync.sync_external_states',
                'schedule_type': Schedule.DAILY
            },
            {
                'name': 'Recommendation Score Re-evaluation',
                'func': 'vibarr.tasks.discovery.recommendations.revaluate_all_recommendations',
                'schedule_type': Schedule.DAILY
            }
        ]

        count = 0
        updated = 0
        for s in schedules:
            obj, created = Schedule.objects.update_or_create(
                name=s['name'],
                defaults={
                    'func': s['func'],
                    'schedule_type': s['schedule_type'],
                    'minutes': s.get('minutes'),
                    'kwargs': s.get('kwargs', {}),
                }
            )
            if created:
                count += 1
                self.stdout.write(self.style.SUCCESS(f"Created schedule: {s['name']}"))
            else:
                updated += 1
                self.stdout.write(self.style.WARNING(f"Updated schedule: {s['name']}"))

        self.stdout.write(self.style.SUCCESS(f"Successfully initialized schedules ({count} created, {updated} updated)."))
