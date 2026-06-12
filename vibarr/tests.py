import logging
from django.test import TestCase, Client
from django.urls import reverse, get_resolver, URLPattern, URLResolver
from django.urls.exceptions import NoReverseMatch
from django.http import HttpResponse
from .models import AppConfig, Persona, Show, ShowState, MediaType

class FailOnErrorHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.errors = []

    def emit(self, record):
        if record.levelno >= logging.ERROR:
            self.errors.append(record)

class VibarrTestCase(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self._log_handler = FailOnErrorHandler()
        logging.getLogger().addHandler(self._log_handler)

    def tearDown(self) -> None:
        logging.getLogger().removeHandler(self._log_handler)
        if self._log_handler.errors:
            error_msgs = "\n".join([f"- {r.name} [{r.levelname}]: {r.getMessage()}" for r in self._log_handler.errors])
            self.fail(f"Unexpected ERROR or CRITICAL logs were generated during test:\n{error_msgs}")
        super().tearDown()

class AppConfigTestCase(VibarrTestCase):
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

class PersonaTestCase(VibarrTestCase):
    def test_persona_creation(self) -> None:
        persona: Persona = Persona.objects.create(
            name="Kids Persona",
            max_content_rating="PG",
            ignored_genres="Horror, Reality TV"
        )
        self.assertEqual(persona.name, "Kids Persona")
        self.assertEqual(str(persona), "Kids Persona")

class ShowTestCase(VibarrTestCase):
    def setUp(self) -> None:
        super().setUp()
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

class ViewsTestCase(VibarrTestCase):
    def setUp(self) -> None:
        super().setUp()
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


class GovernanceTestCase(VibarrTestCase):
    def setUp(self) -> None:
        super().setUp()
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

from unittest.mock import patch, MagicMock
from .models import MediaWatchEvent
from .utils.intelligence import get_weighted_history_profile
from .services.discovery.heuristic_ranking import HeuristicRankingService

class HistoryProfilingTestCase(VibarrTestCase):
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

class RobustAIJsonParsingTestCase(VibarrTestCase):
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

class RouteScannerTestCase(VibarrTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client = Client()
        self.config = AppConfig.get_solo()
        self.config.setup_complete = True
        
        # Disable authentication requirement during scan to avoid 302 redirects to login
        from .models import AuthMode
        self.config.auth_mode = AuthMode.NONE
        self.config.save()
        
        # Create a dummy show for show_id lookups
        from .models import Show, MediaType
        Show.objects.get_or_create(
            id=1,
            defaults={
                'title': 'Test Show',
                'tmdb_id': 9999,
                'media_type': MediaType.SHOW
            }
        )
        
        # Create a persona for switcher/lookup
        from .models import Persona
        Persona.objects.get_or_create(id=1, defaults={'name': 'Test Persona'})

    @patch('requests.request')
    @patch('requests.Session.send')
    @patch('requests.get')
    @patch('requests.post')
    @patch('requests.put')
    @patch('requests.delete')
    def test_dynamic_route_scanner(self, mock_delete, mock_put, mock_post, mock_get, mock_send, mock_request) -> None:
        from unittest.mock import MagicMock
        
        # Setup standard mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'authToken': 'mock-token',
            'id': 1,
            'code': 'ABCD',
            'records': [],
            'results': [],
            'choices': [{'message': {'content': '[]'}}]
        }
        mock_response.text = '{}'
        mock_response.content = b'{}'
        
        mock_request.return_value = mock_response
        mock_send.return_value = mock_response
        mock_get.return_value = mock_response
        mock_post.return_value = mock_response
        mock_put.return_value = mock_response
        mock_delete.return_value = mock_response

        resolver = get_resolver()
        
        def collect_url_names(patterns, prefix=''):
            collected = []
            for pattern in patterns:
                if isinstance(pattern, URLPattern):
                    if pattern.name:
                        collected.append(pattern.name)
                elif isinstance(pattern, URLResolver):
                    collected.extend(collect_url_names(pattern.url_patterns, prefix))
            return list(set(collected))

        url_names = collect_url_names(resolver.url_patterns)
        
        # Standard keyword arguments that endpoints expect
        default_kwargs = {
            'show_id': 1,
            'pin_id': 1,
            'key_id': 1,
            'persona_id': 1,
        }
        
        exempt_urls = [
            'admin:index', 'admin:login', 'admin:logout', 'admin:password_change', 
            'admin:password_change_done', 'admin:jsi18n', 'admin:view_on_site'
        ]
        
        for name in url_names:
            if name.startswith('admin:') or name in exempt_urls:
                continue
                
            url = None
            try:
                url = reverse(name)
            except NoReverseMatch:
                try:
                    url = reverse(name, kwargs=default_kwargs)
                except NoReverseMatch:
                    # Try using individual keyword arguments in case of mismatched signature
                    for key, val in default_kwargs.items():
                        try:
                            url = reverse(name, kwargs={key: val})
                            break
                        except NoReverseMatch:
                            continue
            
            if not url:
                continue
                
            response = self.client.get(url)
            
            self.assertLess(
                response.status_code, 
                500, 
                msg=f"Endpoint '{name}' at URL '{url}' returned status code {response.status_code}."
            )

class TraktAndSeerrTestCase(VibarrTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.config = AppConfig.get_solo()
        self.config.trakt_client_id = "mock_client_id"
        self.config.trakt_username = "mock_user"
        self.config.use_seerr = True
        self.config.h_seerr_tag_weight = 80
        self.config.save()

    @patch('requests.get')
    def test_trakt_service_connection(self, mock_get) -> None:
        from .services.discovery.trakt_service import TraktService
        
        # Test success (200)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        service = TraktService()
        self.assertTrue(service.test_connection())
        
        # Test failure (500)
        mock_response.status_code = 500
        self.assertFalse(service.test_connection())

    @patch('requests.get')
    def test_trakt_related_movies(self, mock_get) -> None:
        from .services.discovery.trakt_service import TraktService
        
        # Setup mock responses for TMDB ID resolution and related movies list
        mock_resolve = MagicMock()
        mock_resolve.status_code = 200
        mock_resolve.json.return_value = [{"movie": {"ids": {"trakt": 1234}}}]
        
        mock_related = MagicMock()
        mock_related.status_code = 200
        mock_related.json.return_value = [{"movie": {"title": "Inception", "ids": {"tmdb": 272}}}]
        
        mock_get.side_effect = [mock_resolve, mock_related]
        
        service = TraktService()
        related = service.get_related_movies(272)
        self.assertEqual(len(related), 1)
        self.assertEqual(related[0]["movie"]["title"], "Inception")

    @patch('requests.get')
    def test_trakt_importer_history(self, mock_get) -> None:
        from .services.discovery.trakt_import import import_trakt_history_from_api
        
        mock_history = MagicMock()
        mock_history.status_code = 200
        mock_history.json.return_value = [
            {
                "id": 99991,
                "type": "movie",
                "watched_at": "2026-06-02T16:14:39.000Z",
                "movie": {
                    "title": "Interstellar",
                    "ids": {"tmdb": 157336}
                }
            }
        ]
        mock_get.return_value = mock_history
        
        imported = import_trakt_history_from_api("mock_user")
        self.assertEqual(imported, 1)
        
        # Verify event was created
        event = MediaWatchEvent.objects.get(event_id="trakt_history_99991")
        self.assertEqual(event.show_title, "Interstellar")
        self.assertEqual(event.tmdb_id, 157336)
        self.assertEqual(event.media_type, MediaType.MOVIE)

    def test_trakt_importer_csv(self) -> None:
        from .services.discovery.trakt_import import import_trakt_csv
        
        csv_data = """title,tmdb_id,type,watched_at
Gladiator,155,movie,2026-06-02 16:14:39
The Matrix,603,movie,2026-06-02 16:14:39
"""
        imported = import_trakt_csv(csv_data)
        self.assertEqual(imported, 2)
        
        # Verify first event
        self.assertTrue(MediaWatchEvent.objects.filter(show_title="Gladiator", tmdb_id=155).exists())
        # Verify second event
        self.assertTrue(MediaWatchEvent.objects.filter(show_title="The Matrix", tmdb_id=603).exists())

    @patch('vibarr.services.managers.seerr_service.SeerrService.get_requests')
    @patch('vibarr.services.discovery.tmdb_service.TMDBService.get_movie_details')
    def test_seerr_tag_heuristic_scoring(self, mock_details, mock_get_requests) -> None:
        # Mock Seerr requests with custom tags
        mock_get_requests.return_value = [
            {
                "media": {"tmdbId": 12},
                "tags": [{"id": 1, "name": "cyberpunk"}, "neon"]
            },
            {
                "media": {"tmdbId": 13},
                "tags": [{"id": 1, "name": "cyberpunk"}]
            },
            {
                "media": {"tmdbId": 14},
                "tags": [{"id": 1, "name": "cyberpunk"}]
            }
        ]
        
        # Mock candidate details showing cyberpunk keyword
        mock_details.return_value = {
            'genres': [{'id': 28, 'name': 'Action'}],
            'keywords': {'keywords': [{'id': 101, 'name': 'cyberpunk'}]}
        }
        
        hrs = HeuristicRankingService()
        
        # Build profile and mock seerr profiles
        profile = hrs._build_user_profile(MediaType.MOVIE)
        seerr_profile = {12}
        seerr_tag_profile = hrs._build_seerr_tag_profile()
        
        self.assertIn("cyberpunk", seerr_tag_profile)
        self.assertIn("neon", seerr_tag_profile)
        
        # Score a candidate matching the tag
        candidate = {
            'id': 100,
            'title': 'Blade Runner',
            'vote_average': 8.0,
            'popularity': 50.0,
            'genre_ids': [28]
        }
        
        score_data = hrs._calculate_score(candidate, MediaType.MOVIE, profile, seerr_profile, seerr_tag_profile)
        self.assertIn("aligns with your request tags", score_data["reasoning"])
        self.assertGreater(score_data["score"], 0)


class UniverseArchitectTestCase(VibarrTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client = Client()
        self.config = AppConfig.get_solo()
        self.config.setup_complete = True
        self.config.save()
        
        # Create some shows in universes
        self.show1 = Show.objects.create(
            title="Marvel Movie",
            tmdb_id=101,
            media_type=MediaType.MOVIE,
            universe_name="Marvel Cinematic Universe",
            state=ShowState.SUGGESTED
        )
        self.show2 = Show.objects.create(
            title="Star Wars Movie",
            tmdb_id=102,
            media_type=MediaType.MOVIE,
            universe_name="Star Wars",
            state=ShowState.SUGGESTED
        )
        # Add recommendation for show1 to make sure reanalysis doesn't fail on missing rec
        from .models import Recommendation
        Recommendation.objects.create(
            suggested_show=self.show1,
            source_title="Marvel Movie",
            score=7.5,
            reasoning="Part of MCU."
        )

    def test_universe_list_view_alphabetical_sorting(self) -> None:
        url = reverse('universe_architect_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        universes = response.context['universes']
        self.assertEqual(len(universes), 2)
        # Alphabetically: "Marvel Cinematic Universe" then "Star Wars"
        self.assertEqual(universes[0]['name'], "Marvel Cinematic Universe")
        self.assertEqual(universes[1]['name'], "Star Wars")
        
        # Check alphabet and active letters
        self.assertIn('M', response.context['active_letters'])
        self.assertIn('S', response.context['active_letters'])
        self.assertIn('A', response.context['alphabet'])

    @patch('vibarr.views.universe.async_task')
    def test_refresh_universe_view(self, mock_async_task) -> None:
        url = reverse('refresh_universe')
        # Empty universe parameter should redirect
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, 302)
        
        # Valid universe name should trigger discover_universe_and_sync task
        response = self.client.post(url, {'universe': 'Star Wars'})
        self.assertEqual(response.status_code, 302)
        mock_async_task.assert_called_once_with('vibarr.tasks.managers.sync.discover_universe_and_sync', self.show2.id)

    @patch('vibarr.views.universe.async_task')
    def test_reanalyze_universe_view(self, mock_async_task) -> None:
        url = reverse('reanalyze_universe')
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, 302)
        
        response = self.client.post(url, {'universe': 'Marvel Cinematic Universe'})
        self.assertEqual(response.status_code, 302)
        mock_async_task.assert_called_once_with('vibarr.tasks.managers.sync.reevaluate_universe_shows', 'Marvel Cinematic Universe')

    @patch('vibarr.tasks.discovery.recommendations.reevaluate_single_show')
    def test_reevaluate_universe_shows_task(self, mock_reevaluate) -> None:
        from .tasks.managers.sync import reevaluate_universe_shows
        reevaluate_universe_shows('Marvel Cinematic Universe')
        mock_reevaluate.assert_called_once_with(self.show1)

    def test_multiple_universes_on_show(self) -> None:
        from .models.universe import Universe
        universe2 = Universe.objects.create(name="Multiverse")
        self.show1.universes.add(universe2)
        
        self.assertEqual(self.show1.universes.count(), 2)
        names = [u.name for u in self.show1.universes.all()]
        self.assertIn("Marvel Cinematic Universe", names)
        self.assertIn("Multiverse", names)

    def test_merge_universes_view(self) -> None:
        url = reverse('merge_universes')
        response = self.client.post(url, {
            'source_universe': 'Star Wars',
            'target_universe': 'Marvel Cinematic Universe'
        })
        self.assertEqual(response.status_code, 302)
        
        from .models.universe import Universe
        self.assertFalse(Universe.objects.filter(name='Star Wars').exists())
        
        self.show2.refresh_from_db()
        self.assertTrue(self.show2.universes.filter(name='Marvel Cinematic Universe').exists())
        self.assertEqual(self.show2.universe_name, 'Marvel Cinematic Universe')

    def test_dismiss_suggestion_view(self) -> None:
        from .models.universe import Universe, UniverseMergeSuggestion
        univ1 = Universe.objects.get(name="Marvel Cinematic Universe")
        univ2 = Universe.objects.get(name="Star Wars")
        sug = UniverseMergeSuggestion.objects.create(
            source_universe=univ2,
            target_universe=univ1,
            confidence=8,
            reasoning="Crossover suggestion"
        )
        
        url = reverse('dismiss_suggestion', kwargs={'suggestion_id': sug.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        
        self.assertFalse(UniverseMergeSuggestion.objects.filter(id=sug.id).exists())

    @patch('vibarr.services.discovery.ai_service.AIService.analyze_universe_ecosystem')
    def test_analyze_universe_ecosystem_task(self, mock_analyze) -> None:
        from .tasks.managers.sync import analyze_universe_ecosystem_task
        from .models.universe import Universe, UniverseMergeSuggestion
        
        mock_analyze.return_value = [
            {
                "source_universe": "Star Wars",
                "target_universe": "Marvel Cinematic Universe",
                "confidence": 9,
                "reasoning": "Both are Disney properties."
            }
        ]
        
        analyze_universe_ecosystem_task()
        
        suggestions = UniverseMergeSuggestion.objects.all()
        self.assertEqual(suggestions.count(), 1)
        sug = suggestions.first()
        self.assertEqual(sug.confidence, 9)

    def test_analyze_ecosystem_view_initializes_cache(self) -> None:
        from django.core.cache import cache
        cache.clear()
        
        url = reverse('analyze_universe_ecosystem')
        response = self.client.post(url, HTTP_HX_REQUEST='true')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'universe-scan-status-container', response.content)
        
        self.assertTrue(cache.get('universe_scan_running'))
        self.assertEqual(cache.get('universe_scan_progress'), 0)
        self.assertEqual(cache.get('universe_scan_status'), 'Initializing AI Ecosystem analysis...')

    def test_universe_scan_status_view_running(self) -> None:
        from django.core.cache import cache
        cache.set('universe_scan_running', True, 30)
        cache.set('universe_scan_progress', 45, 30)
        cache.set('universe_scan_status', 'Testing progress...', 30)
        
        url = reverse('universe_scan_status')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Testing progress...', response.content)
        self.assertIn(b'45%', response.content)
        self.assertNotIn('HX-Trigger', response.headers)

    def test_universe_scan_status_view_finished_triggers_reload(self) -> None:
        from django.core.cache import cache
        cache.set('universe_scan_running', False, 30)
        cache.set('universe_scan_progress', 100, 30)
        cache.set('universe_scan_status', 'Done', 30)
        
        url = reverse('universe_scan_status')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('HX-Trigger', response.headers)
        self.assertEqual(response.headers['HX-Trigger'], 'refresh-universes')


class LibraryStatusTestCase(VibarrTestCase):
    def test_show_is_downloaded_default(self) -> None:
        show = Show.objects.create(
            title="Test Movie Status",
            tmdb_id=8881,
            media_type=MediaType.MOVIE,
            state=ShowState.SUGGESTED
        )
        self.assertFalse(show.is_downloaded)

    @patch('vibarr.tasks.managers.sync.RadarrService')
    @patch('vibarr.tasks.managers.sync.SonarrService')
    def test_sync_external_states_updates_is_downloaded(self, mock_sonarr, mock_radarr) -> None:
        # Setup mocks
        mock_sonarr_inst = mock_sonarr.return_value
        mock_radarr_inst = mock_radarr.return_value
        
        # Mock Sonarr/Radarr APIs
        mock_sonarr_inst.get_all_series_data.return_value = {
            '9999': {
                'id': 1,
                'monitored': True,
                'seasons': [{'seasonNumber': 1, 'monitored': True}],
                'statistics': {'episodeFileCount': 3}
            }
        }
        
        mock_radarr_inst.get_all_movies_data.return_value = {
            '8883': {
                'id': 2,
                'monitored': True,
                'hasFile': True
            }
        }

        # Create tasting show and committed movie
        show = Show.objects.create(
            title="Test Show Downloaded",
            tmdb_id=8882,
            tvdb_id=9999,
            sonarr_id=1,
            media_type=MediaType.SHOW,
            state=ShowState.TASTING
        )
        movie = Show.objects.create(
            title="Test Movie Downloaded",
            tmdb_id=8883,
            radarr_id=2,
            media_type=MediaType.MOVIE,
            state=ShowState.COMMITTED
        )

        from .tasks.managers.sync import sync_external_states
        sync_external_states()

        # Refresh from DB
        show.refresh_from_db()
        movie.refresh_from_db()

        self.assertTrue(show.is_downloaded)
        self.assertTrue(movie.is_downloaded)

class AIThinkingTestCase(VibarrTestCase):
    def test_default_thinking_fields(self) -> None:
        config = AppConfig.get_solo()
        self.assertFalse(config.ai_thinking)
        self.assertEqual(config.ai_thinking_effort, "medium")

    def test_prepare_payload_thinking_disabled(self) -> None:
        from .services.discovery.ai.base import AIBaseService
        
        config = AppConfig.get_solo()
        config.ai_thinking = False
        config.ai_model = "gpt-4o"
        config.ai_api_url = "https://api.openai.com/v1"
        config.save()
        
        service = AIBaseService()
        payload = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "hello"}],
            "temperature": 0.5
        }
        prepared = service._prepare_payload(payload, json_mode=True)
        
        # Check standard gpt JSON mode formatting applied
        self.assertEqual(prepared["response_format"], {"type": "json_object"})
        # Check thinking keys not added
        self.assertNotIn("reasoning_effort", prepared)
        self.assertNotIn("thinking", prepared)
        self.assertEqual(prepared["temperature"], 0.5)

    def test_prepare_payload_thinking_enabled(self) -> None:
        from .services.discovery.ai.base import AIBaseService
        
        config = AppConfig.get_solo()
        config.ai_thinking = True
        config.ai_thinking_effort = "high"
        config.ai_model = "claude-3-7-sonnet"
        config.ai_api_url = "https://api.anthropic.com/v1"
        config.save()
        
        service = AIBaseService()
        payload = {
            "model": "claude-3-7-sonnet",
            "messages": [{"role": "user", "content": "hello"}],
            "temperature": 0.5
        }
        prepared = service._prepare_payload(payload, json_mode=False)
        
        # Check thinking settings added
        self.assertEqual(prepared["reasoning_effort"], "high")
        self.assertEqual(prepared["thinking"], {"type": "enabled", "budget_tokens": 4096})
        # Check temperature overridden to 1.0
        self.assertEqual(prepared["temperature"], 1.0)


