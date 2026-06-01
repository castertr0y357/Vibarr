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

from unittest.mock import patch
from .models import MediaWatchEvent
from .utils.intelligence import get_weighted_history_profile
from .services.discovery.heuristic_ranking import HeuristicRankingService

class HistoryProfilingTestCase(TestCase):
    def test_get_weighted_history_profile_blending(self) -> None:
        import datetime
        from django.utils import timezone
        
        # Create a user config
        config = AppConfig.get_solo()
        config.show_influence_on_movies = 0
        config.movie_influence_on_shows = 0
        config.save()
        
        base_time = timezone.now()
        
        # 1. Create 5 older, highly-watched shows (Comfort Shows)
        # e.g., watched 5 times each, 10 days ago
        for i in range(5):
            for _ in range(5):
                MediaWatchEvent.objects.create(
                    event_id=f"comfort_{i}_{_}",
                    show_title=f"Comfort Show {i}",
                    media_type=MediaType.SHOW,
                    season=1,
                    episode=1,
                    watched_at=base_time - datetime.timedelta(days=10)
                )
                
        # 2. Create 10 recent, single-watched shows
        # e.g., watched 1 time each, in the last 10 hours
        for i in range(10):
            MediaWatchEvent.objects.create(
                event_id=f"recent_{i}",
                show_title=f"Recent Show {i}",
                media_type=MediaType.SHOW,
                season=1,
                episode=1,
                watched_at=base_time - datetime.timedelta(hours=i)
            )
            
        # Get weighted history profile for SHOW
        profile = get_weighted_history_profile(MediaType.SHOW)
        
        # Profile should contain a blend of both (up to 10 recent and 10 top played)
        titles = [p['title'] for p in profile]
        
        # All 5 comfort shows should be in the profile because they are top played
        for i in range(5):
            self.assertIn(f"Comfort Show {i}", titles)
            
        # Recent shows should be in the profile (at least some, since we took the top 10 recent)
        recent_count = sum(1 for t in titles if "Recent Show" in t)
        self.assertGreater(recent_count, 0)
        
        # Verify fields
        for item in profile:
            self.assertTrue(item['is_primary'])
            self.assertIn('play_count', item)
            if "Comfort Show" in item['title']:
                self.assertEqual(item['play_count'], 5)
            else:
                self.assertEqual(item['play_count'], 1)

    @patch('vibarr.services.discovery.tmdb_service.TMDBService.get_show_details')
    def test_heuristic_user_profile_blending(self, mock_get_show_details) -> None:
        import datetime
        from django.utils import timezone
        
        mock_get_show_details.return_value = {
            'genres': [{'id': 18, 'name': 'Drama'}],
            'keywords': {'results': [{'id': 100, 'name': 'mystery'}]}
        }
        
        base_time = timezone.now()
        
        # Create 5 older, highly-watched shows (Comfort Shows)
        for i in range(5):
            for _ in range(5):
                MediaWatchEvent.objects.create(
                    event_id=f"h_comfort_{i}_{_}",
                    show_title=f"H Comfort Show {i}",
                    tmdb_id=1000 + i,
                    media_type=MediaType.SHOW,
                    season=1,
                    episode=1,
                    watched_at=base_time - datetime.timedelta(days=10)
                )
                
        # Create 10 recent, single-watched shows
        for i in range(10):
            MediaWatchEvent.objects.create(
                event_id=f"h_recent_{i}",
                show_title=f"H Recent Show {i}",
                tmdb_id=2000 + i,
                media_type=MediaType.SHOW,
                season=1,
                episode=1,
                watched_at=base_time - datetime.timedelta(hours=i)
            )
            
        hrs = HeuristicRankingService()
        profile = hrs._build_user_profile(MediaType.SHOW)
        
        # Check that genres/keywords were populated and both recent and comfort shows were queried.
        # We mocked TMDB to return Genre 18 (Drama) and Keyword 100 (mystery).
        # Both genres and keywords dict should have weights showing they processed the items.
        self.assertIn(18, profile['genres'])
        self.assertIn(100, profile['keywords'])
        
        # The genre weight should reflect log-scaled play count sum
        self.assertGreater(profile['genres'][18], 15.0)

class RobustAIJsonParsingTestCase(TestCase):
    def test_robust_ai_json_parsing_repair(self) -> None:
        from .services.discovery.ai.base import AIBaseService
        
        raw_malformed = """```json
[
{
"title": "Full House",
"reasoning": "This is a prime continuation of your comfort viewing, featuring a 'found family' dynamic that resonates strongly with the themes of 'The Golden Girls' and other warm, ensemble sitcoms.",
"vibe_tags": [
"Found Family",
"Sitcom",
"Nostalgic",
"Comedy"
},
{
"title": "Family Matters",
"reasoning": "It is a perfect fit for your preference for dramedy and ensemble comedy, featuring the messy, quirky, and
"""
        service = AIBaseService()
        parsed = service._parse_json_response(raw_malformed, [])
        
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0]['title'], "Full House")
        self.assertEqual(parsed[0]['vibe_tags'], ["Found Family", "Sitcom", "Nostalgic", "Comedy"])
        self.assertEqual(parsed[1]['title'], "Family Matters")
        self.assertTrue(parsed[1]['reasoning'].startswith("It is a perfect fit"))

    def test_robust_ai_json_parsing_repair_discard_truncated(self) -> None:
        from .services.discovery.ai.base import AIBaseService
        
        raw_severely_truncated = """```json
[
{
"title": "Full House",
"reasoning": "This is a prime continuation of your comfort viewing.",
"vibe_tags": [
"Found Family",
"Sitcom",
"Nostalgic",
"Comedy"
},
{
"title": "Family Matters",
"reason
"""
        service = AIBaseService()
        parsed = service._parse_json_response(raw_severely_truncated, [])
        
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]['title'], "Full House")
        self.assertEqual(parsed[0]['vibe_tags'], ["Found Family", "Sitcom", "Nostalgic", "Comedy"])
