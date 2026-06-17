from django.db import migrations

def seed_default_personas(apps, schema_editor):
    Persona = apps.get_model('vibarr', 'Persona')
    AppConfig = apps.get_model('vibarr', 'AppConfig')
    
    # Check if any Persona already exists
    if not Persona.objects.exists():
        adult = Persona.objects.create(name="Adult", max_content_rating="R", ignored_genres="")
        family = Persona.objects.create(name="Family", max_content_rating="PG-13", ignored_genres="Horror")
        kids = Persona.objects.create(name="Kids", max_content_rating="G", ignored_genres="Horror, Thriller")
        
        # Set active_persona in AppConfig if it exists and doesn't have one
        config = AppConfig.objects.first()
        if config and not config.active_persona:
            config.active_persona = adult
            config.save()

def rollback_default_personas(apps, schema_editor):
    Persona = apps.get_model('vibarr', 'Persona')
    Persona.objects.filter(name__in=["Adult", "Family", "Kids"]).delete()

class Migration(migrations.Migration):

    dependencies = [
        ('vibarr', '0049_appconfig_ai_thinking_appconfig_ai_thinking_effort'),
    ]

    operations = [
        migrations.RunPython(seed_default_personas, rollback_default_personas),
    ]
