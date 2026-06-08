from django.db import migrations

def migrate_universe_names(apps, schema_editor):
    Show = apps.get_model('vibarr', 'Show')
    Universe = apps.get_model('vibarr', 'Universe')

    for show in Show.objects.filter(universe_name__isnull=False).exclude(universe_name=''):
        # Normalize and strip whitespace
        u_name = show.universe_name.strip()
        if u_name:
            universe, _ = Universe.objects.get_or_create(name=u_name)
            show.universes.add(universe)

def reverse_migrate_universe_names(apps, schema_editor):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('vibarr', '0047_universe_universemergesuggestion_show_universes_and_more'),
    ]

    operations = [
        migrations.RunPython(migrate_universe_names, reverse_migrate_universe_names),
    ]
