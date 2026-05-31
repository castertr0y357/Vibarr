from django.test import TestCase, Client
from django.urls import reverse
from django.http import HttpResponse
from .models import AppConfig, Persona, Show, ShowState, MediaType

class AppConfigTestCase(TestCase):
    def test_singleton_get_solo(self) -> None:
        # get_solo should create one config
        config: AppConfig = AppConfig.get_solo()
        self.assertIsNotNone(config)
        self.assertEqual(AppConfig.objects.count(), 1)
        
        # Subsequent get_solo calls should return the same instance
        config2: AppConfig = AppConfig.get_solo()
        self.assertEqual(config.pk, config2.pk)
        self.assertEqual(AppConfig.objects.count(), 1)

    def test_singleton_save_enforcement(self) -> None:
        config: AppConfig = AppConfig.get_solo()
        # Attempt to save a second config directly
        extra_config: AppConfig = AppConfig()
        extra_config.save()
        self.assertEqual(AppConfig.objects.count(), 1)

    def test_singleton_delete_prevention(self) -> None:
        config: AppConfig = AppConfig.get_solo()
        config.delete()
        self.assertEqual(AppConfig.objects.count(), 1)

class PersonaTestCase(TestCase):
    def test_persona_creation(self) -> None:
        persona: Persona = Persona.objects.create(
            name="Kids Persona",
            max_content_rating="PG",
            ignored_genres="Horror, Reality TV"
        )
        self.assertEqual(persona.name, "Kids Persona")
        self.assertEqual(str(persona), "Kids Persona")

class ShowTestCase(TestCase):
    def setUp(self) -> None:
        self.config: AppConfig = AppConfig.get_solo()
        self.kids_persona: Persona = Persona.objects.create(
            name="Kids",
            max_content_rating="PG"
        )
        self.adult_persona: Persona = Persona.objects.create(
            name="Adults",
            max_content_rating="R"
        )

    def test_rating_threshold(self) -> None:
        # Show with TV-MA rating
        show: Show = Show.objects.create(
            title="Grimm",
            tmdb_id=12345,
            media_type=MediaType.SHOW,
            content_rating="TV-MA"
        )
        
        # Default global setting is TV-14 (RATING_SCALE = 3). TV-MA is RATING_SCALE = 4.
        self.config.max_content_rating = "TV-14"
        self.config.active_persona = None
        self.config.save()
        self.assertTrue(show.is_above_threshold)

        # Set active persona to Adults (max rating R = 4)
        self.config.active_persona = self.adult_persona
        self.config.save()
        # TV-MA (4) is not above Adults R (4)
        self.assertFalse(show.is_above_threshold)

        # Set active persona to Kids (max rating PG = 2)
        self.config.active_persona = self.kids_persona
        self.config.save()
        # TV-MA (4) is above Kids PG (2)
        self.assertTrue(show.is_above_threshold)

class ViewsTestCase(TestCase):
    def setUp(self) -> None:
        self.client: Client = Client()
        self.config: AppConfig = AppConfig.get_solo()
        # Setup finished/configured to bypass Wizard settings redirect
        self.config.setup_complete = True
        self.config.save()

    def test_dashboard_view(self) -> None:
        url: str = reverse('dashboard')
        response: HttpResponse = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_settings_view(self) -> None:
        url: str = reverse('settings')
        response: HttpResponse = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_settings_general_view(self) -> None:
        url: str = reverse('settings_general')
        response: HttpResponse = self.client.get(url)
        self.assertEqual(response.status_code, 200)
