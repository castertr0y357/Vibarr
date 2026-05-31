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


class GovernanceTestCase(TestCase):
    def setUp(self) -> None:
        self.config: AppConfig = AppConfig.get_solo()
        self.config.max_discovered_shows = 2
        self.config.max_discovered_movies = 2
        self.config.save()

    def test_prune_discovery_backlog_shows(self) -> None:
        from .tasks.discovery.recommendations import prune_discovery_backlog
        from .models import Recommendation
        
        # Create 3 suggested shows
        show1 = Show.objects.create(title="Show 1", tmdb_id=1, media_type=MediaType.SHOW, state=ShowState.SUGGESTED)
        Recommendation.objects.create(suggested_show=show1, source_title="Seed", score=8.5)
        
        show2 = Show.objects.create(title="Show 2", tmdb_id=2, media_type=MediaType.SHOW, state=ShowState.SUGGESTED)
        Recommendation.objects.create(suggested_show=show2, source_title="Seed", score=9.2)
        
        show3 = Show.objects.create(title="Show 3", tmdb_id=3, media_type=MediaType.SHOW, state=ShowState.SUGGESTED)
        Recommendation.objects.create(suggested_show=show3, source_title="Seed", score=7.1)
        
        self.assertEqual(Show.objects.filter(state=ShowState.SUGGESTED, media_type=MediaType.SHOW).count(), 3)
        
        # Pruning should keep top 2, meaning Show 3 (score 7.1) should be pruned
        prune_discovery_backlog(MediaType.SHOW)
        
        self.assertEqual(Show.objects.filter(state=ShowState.SUGGESTED, media_type=MediaType.SHOW).count(), 2)
        self.assertTrue(Show.objects.filter(id=show1.id).exists())
        self.assertTrue(Show.objects.filter(id=show2.id).exists())
        self.assertFalse(Show.objects.filter(id=show3.id).exists())

    def test_prune_discovery_backlog_pinned_protection(self) -> None:
        from .tasks.discovery.recommendations import prune_discovery_backlog
        from .models import Recommendation

        # Create 3 suggested shows. Show 3 has the lowest score but is pinned.
        show1 = Show.objects.create(title="Show 1", tmdb_id=1, media_type=MediaType.SHOW, state=ShowState.SUGGESTED)
        Recommendation.objects.create(suggested_show=show1, source_title="Seed", score=8.5)
        
        show2 = Show.objects.create(title="Show 2", tmdb_id=2, media_type=MediaType.SHOW, state=ShowState.SUGGESTED)
        Recommendation.objects.create(suggested_show=show2, source_title="Seed", score=9.2)
        
        show3 = Show.objects.create(title="Show 3", tmdb_id=3, media_type=MediaType.SHOW, state=ShowState.SUGGESTED, is_pinned=True)
        Recommendation.objects.create(suggested_show=show3, source_title="Seed", score=7.1)
        
        # Pruning should keep Show 3 because it is pinned. It should prune Show 1 (score 8.5, unpinned) instead of Show 3 (score 7.1, pinned)
        prune_discovery_backlog(MediaType.SHOW)
        
        self.assertEqual(Show.objects.filter(state=ShowState.SUGGESTED, media_type=MediaType.SHOW).count(), 2)
        self.assertFalse(Show.objects.filter(id=show1.id).exists())
        self.assertTrue(Show.objects.filter(id=show2.id).exists())
        self.assertTrue(Show.objects.filter(id=show3.id).exists())
