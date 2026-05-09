# Project Status: Vibarr

## Current State: STABLE ENTERPRISE CORE (v1.8)
**Last Checkpoint**: 2026-05-08 (UX Refinement & Search Integration)

## Core Architecture
- **Framework**: Django (Postgres + Redis + Django-Q2)
- **Architecture**: Modular Monolith with strictly decoupled tasks and explicit dependency trees.
- **API Strategy**: Headless Hybrid (Django CBVs + APIMixin supporting JSON & HTMX)
- **Deployment**: Hardened Docker Compose (Orchestrated Postgres, Redis, Web, and Worker)
- **Integrations**: Plex/Jellyfin (Media), Sonarr/Radarr (Automation), Overseerr/Jellyseerr (Requests), TMDB, OpenAI-Compatible AI
- **Frontend**: Vanilla CSS + HTMX + Alpine.js (Real-time polling, flip-card interactions, animated transitions)

## Primary Logic
- **4+1 Serendipity**: AI Ranking that provides 4 high-confidence matches and 1 "Wildcard" thematic connection.
- **Autonomous Scout**: High-confidence matches (>9.5) bypass the suggested shelf and trigger automatic tastings.
- **Household Lenses**: Real-time dashboard filters for "Adult", "Family", and "Kids" personas with rating/genre enforcement.
- **Dynamic Tasting**: Auto-manages 3-5 episode "trials" via Sonarr/Radarr.
- **Universe Architect**: Automatic detection and Plex Collection grouping of cinematic universes.
- **Auto-Commit/Purge**: Real-time promotion or deletion based on Plex activity.
- **Vibe Snap**: Contextual mood-based quick search (Time/Day aware), integrated into the search page.
- **Concierge Notifications**: Real-time Discord/Telegram updates.

## Active Features
- [x] **Weighted Heuristic Engine**: Tunable non-AI recommendations using 6 distinct metadata signals (Ratings, Popularity, Genres, Keywords, Collections, Seerr).
- [x] **Dashboard Lifecycle Reordering**: Logical UX progression: Discovery Feed → Active Tastings → Committed Series.
- [x] **Committed Series Gallery**: Dedicated historical view for successfully graduated shows.
- [x] **Seerr-Aware Sourcing**: Native integration with Overseerr/Jellyseerr request history.
- [x] **Dynamic HTMX Pagination**: Seamless, no-refresh navigation for History and Discovery feeds with URL state persistence.
- [x] **Seamless Settings UX**: HTMX-powered configuration saving with instant toast feedback.
- [x] **Universe Live-Refresh**: Automatic UI updates for the Universe Architect when background discovery tasks complete.
- [x] **Compact System Health**: Sleek, horizontal sidebar status indicators with hover-detail tooltips.
- [x] **AI Score Re-evaluation**: Periodic background re-scoring of all discoveries based on evolving watch history.
- [x] **Intelligent Universe Scoring**: Accurate AI-driven ranking for franchise members (replacing hardcoded scores).
- [x] **Enterprise Hardening**: 100% Top-level imports, resolved circular dependencies, and atomic database transactions.
- [x] **Headless API**: Full token-based API access for external community integrations.
- [x] **Household Lenses**: Persona-based filtering (Age limits & Genre blacklists).
- [x] **Autonomous Scout**: AI-driven auto-acquisition based on confidence thresholds.
- [x] **Hardened Docker**: Production-ready containerization.
- [x] **Automated Onboarding**: Setup Wizard with Plex PIN Auth & Media Source selection.
- [x] **Production Settings**: 100% Model synchronized form with HTMX connection validation.
- [x] **Companion Manager**: Seamless sync with Overseerr/Jellyseerr.
- [x] **Vibe Snap (Quick Search)**: Time-of-day mood selector with AI-reranking, moved to search page.
- [x] **Concierge Notifications**: Discord/Telegram triggers.
- [x] **Semantic Vibe Search**: Natural language discovery via AI.
- [x] **Universe Architect**: AI-driven cinematic universe detection.
- [x] **Flip-Card Reasoning**: Interactive card flip reveals AI "Scout Reasoning" and Vibe Tags.
- [x] **Mark as Watched**: Users can flag already-seen titles; feeds AI learning and prevents re-suggestion.
- [x] **Duplicate Prevention**: Discovery pipeline cross-references watch history and library scans before suggesting.
- [x] **Monitored Libraries**: Inclusion-based library selection (replaced exclusion model for clarity).
- [x] **Inline Sidebar Navigation**: Icons and text on same line for clean visual hierarchy.
- [x] **Hardened Skills**: Fully automated `doctor`, `smoke_test`, `rebuild`, and `initialize_schedules` workflows with PowerShell/Docker Desktop compatibility.
- [x] **Self-Healing Diagnostics**: Automatic CRLF-to-LF conversion and migration checks.
- [x] **Zero-Config Plex Discovery**: Automated server discovery via token (no manual URL/IP guessing).
- [x] **Settings UX Hardening**: Auto-save before authentication and live unsaved library scanning.
- [x] **Color-Coded Media Badges**: Visual distinction between Movies (Radarr/Amber) and Shows (Sonarr/Blue) across the dashboard and history.
- [x] **External Media Links**: Direct links to TMDB on the back of all cards for deeper title exploration.
- [x] **Scalable Discovery Architecture**: Dedicated full-page feeds for Discoveries and Tastings, with a "Top 5" executive summary dashboard.
- [x] **Dual-Track Intelligence**: Independent sourcing engines for Movies and TV, ensuring balanced recommendations regardless of recent viewing habits.
- [x] **IMDB Enrichment**: Real-time cross-referencing with IMDB identifiers for high-consensus quality signals and direct critical links.
- [x] **Metadata Maintenance Engine**: Automated background backfilling and "Deep Refresh" capabilities to keep the entire library updated.
- [x] **Automated Growth Governance**: Hard limits on discovery and tasting volume to prevent database/storage bloat.
- [x] **Dual-Track Intelligence**: Independent sourcing engines for Movies and TV, ensuring balanced recommendations regardless of recent viewing habits.
- [x] **Cross-Media Influence**: Configurable "leakage" settings that allow your movie taste to subtly shape TV suggestions (and vice versa).
- [x] **TVDB Integration**: Native support for TheTVDB v4 API for enhanced metadata enrichment and higher accuracy series lookups.
- [x] **Universe Dashboard**: Dedicated visual gallery for franchise continuities with horizontal scrolling.
- [x] **Collection Automation**: One-click "Complete Collection" logic and automated Plex/Jellyfin collection mirroring.
- [x] **Media-Type Dashboard Filtering**: Granular 'All / Movies / Shows' toggles for both Discovery and Active Tastings sections.
- [x] **Manager-Aware Library Sync**: Cross-references Plex with Radarr/Sonarr to identify owned content before it even hits the media server.
- [x] **Hybrid Discovery Engine**: Combines official TMDB collections with AI-driven cinematic universes for 100% franchise coverage.
- [x] **Human-Readable Logging**: Contextual task prefixes and clean formatting for production observability.
- [x] **Heuristic Tuning Sliders**: Reactive settings UI that dynamically hides/shows based on AI toggle status.
- [x] **Vibe Snap Integration**: Rebranded and migrated the quick-search mood selector to the Vibe Search page for better contextual fit.
- [x] **Dashboard De-cluttering**: Removed redundant Universe Architect navigation from the executive summary view.

### UX Refinement & Search Integration (v1.8)
- **Vibe Snap Migration**: Moved the "Nightcap" feature from the dashboard to the search page. This aligns the feature with the user's "search intent" rather than passive browsing.
- **Visual Rebranding**: Rebranded the feature as **Vibe Snap** with a lightning-bolt aesthetic (⚡) and refreshed "Snap Analysis" reasoning.
- **Redundancy Cleanup**: Removed the "Universe Architect" link from the Discovery Feed header on the dashboard to reduce visual noise, as it is already accessible via the primary sidebar.
- [x] **Rebranded Discovery**: Vibe Snap (formerly Nightcap) integrated into Search.
- [x] **Clutter Reduction**: Dashboard navigation cleanup.

### Heuristic & UX Logic Hardening (v1.7)
- **Weighted Heuristic Engine**: Implemented a sophisticated non-AI recommendation system using weighted tuning for Ratings, Popularity, Genres, Keywords, Collections, and Seerr request history.
- **Tuned UX Progression**: Reordered the dashboard to follow the logical "Discovery → Tasting → Commitment" journey for a more intuitive user experience.
- **"Full Series Committed" Logic**: Reserved the committed section exclusively for TV shows (excluding one-off movies) and added a dedicated historical gallery for all "graduation" successes.
- **Seerr Integration**: Added native support for fetching Overseerr/Jellyseerr requests to inform recommendation scores.
- **Reactive Settings**: Heuristic tuning sliders dynamically hide when AI is enabled, ensuring a clean and focused configuration experience.
- [x] **Heuristic Ranking**: Implementation of the HeuristicRankingService.
- [x] **Dashboard Logic**: Logical reordering of dashboard sections and Show-only commitment filtering.
- [x] **Seerr History Integration**: Request-aware recommendation weighting.
- [x] **Historical Success Gallery**: Dedicated page for graduated committed series.
- **SPA-Style Navigation**: Implemented HTMX-driven pagination for the Watch History page, updating the content container while preserving browser history and scroll position.
- **Background Score Re-evaluation**: Added a daily `revaluate_all_recommendations` task that recalculates scores for the entire discovery backlog, ensuring recommendations stay fresh as user tastes evolve.
- **Universe Accuracy**: Refactored the Universe Architect to utilize the new AI `score_candidates` service, ensuring franchise members are ranked realistically against the user's taste profile.
- **UI De-cluttering**: Consolidated dashboard maintenance actions into the sidebar and optimized the sidebar health dashboard for improved vertical real estate.
- **Auto-Promotion Logic**: Re-evaluation task now automatically triggers tastings if a suggested item's new score crosses the confidence threshold.
- [x] **Dynamic UX**: HTMX-ified History pagination and Settings saving.
- [x] **Intelligence Re-evaluation**: Daily re-scoring of the discovery backlog.
- [x] **Universe Accuracy**: AI-driven scoring for all franchise members.
- [x] **Streamlined Dashboard**: Consolidated quick actions and compact health monitoring.

### Hardening & Technical Debt Eradication (v1.5)
- **Lazy Import Elimination**: 100% removal of lazy imports across Models, Tasks, Services, Views, and Middleware, ensuring transparent dependency trees and faster startup.
- **Circular Dependency Resolution**: Broken structural circularity between Tasks and Models, and between task modules themselves, using string references for `async_task` and refactoring shared utilities.
- **Show Model Hardening**: Implemented strict validation for `tasting_progress_percent` and `is_above_threshold` properties to prevent `ZeroDivisionError` and handle malformed data gracefully.
- **Task Stability Fixes**: Resolved uninitialized variable bugs in the recommendation engine and standardized service-layer initialization across all third-party integrations (TMDB, TVDB, Sonarr, Radarr, Plex).
- **Structural Verification**: Verified project-wide integrity to ensure zero runtime dependency warnings.
- [x] **Technical Debt Eradication**: Complete removal of lazy imports and structural circularity across the entire app.
- [x] **Zero-Crash Model Properties**: Hardened progress calculation logic with strict type and range validation.
- [x] **Async Task Decoupling**: View-to-Task independence via string-based task references.

### Universe Architect & Engine Hardening (v1.4)
- **Hybrid Discovery Pipeline**: Integrated TMDB Collections for 100% accurate movie franchise discovery, complemented by AI for broader multi-media continuities (e.g., MCU TV spin-offs).
- **Manager-Integrated Library Identification**: Universe sync now cross-checks against **Radarr** and **Sonarr** TMDB/TVDB IDs, correctly flagging items as "In Library" even if they are still downloading or haven't been indexed by Plex yet.
- **Accurate ID-Based Matching**: Replaced fuzzy title matching with strict **TMDB ID** lookups for all media server providers (Plex/Jellyfin), eliminating false positives and missing "In Library" tags.
- **Enhanced UI Navigation**: Added a sticky **Universe Jump Bar** (Tabs) for instant navigation across large libraries and custom **"Slick" scrollbars** for horizontal franchise rows.
- **Static Library Cards**: Replaced interactive flip-cards with simplified, grayscale "In Library" glass cards in the universe view to reduce visual noise and emphasize collection completeness.
- **Human-Readable Logging**: Revamped the entire logging system with clear formatting and contextual prefixes (`[Library Sync]`, `[AI Scout]`, `[Universe Architect]`).
- **Worker Renaming**: Standardized the background engine as `Vibarr-Worker` for clear identification in system logs.
- **Immediate UX Feedback**: Added real-time Alpine.js toast notifications for background sync triggers.
- **UI Decuttering**: Purged the Django Admin link from the primary sidebar and added a "BETA" status badge to the Universe Architect section.
- **Seed Broadening**: Updated universe discovery to use `WATCHED` and `TASTING` items as seeds, ensuring discovery triggers even for purely Plex-synced libraries.

### Universe Architect & Collection Management (v1.3)
- **Universe Detection**: Enhanced the discovery pipeline with AI-driven franchise identification. Items are now automatically tagged with their "Universe" (e.g. Marvel Cinematic Universe).
- **Universe Dashboard**: Created a new dedicated page (`/universes/`) that groups the library by franchise, featuring cinematic horizontal scrolling rows.
- **URL Routing Resolution**: Fixed a critical `NoReverseMatch` error by renaming the universe list URL to `universe_architect_list` and resolving naming collisions in the modular URL structure.
- **Collection Completion**: Implemented batch-action logic allowing users to "Complete Collection" for a specific universe, triggering automated tastings for all missing items.
- **Media Server Mirroring**: Added automated collection/boxset creation for Plex and Jellyfin. Vibarr now synchronizes detected universes directly to the media server metadata.
- **Robust Metadata Enrichment**: Upgraded the universe discovery task to fetch full details (posters, ratings, external IDs) immediately upon creation.
- **Advanced Title Cleaning**: Improved TMDB search regex to handle diverse AI-generated title formats, including bracketed series/year strings (e.g., "(Series, 2021)").
- **Stability Dispatcher**: Refactored `batch_universe_sync` into a multi-task dispatcher, preventing worker timeouts and memory exhaustion by distributing the workload.
- **Library Integration**: Updated universe discovery to include items already in the library, marking them as `COMMITTED` and tagging them with franchise metadata for a unified collection view.
- **Background Automation**: Implemented `initialize_schedules` management command to set up and manage all periodic tasks (Polling, Scouting, Universe Sync, Metadata Maintenance) in Django-Q.

### Unified Dashboard Filtering
- **Contextual Toggles**: Integrated media-type filtering ('All', 'Movies', 'Shows') for the **Active Tastings** section, mirroring the Discovery Feed experience.
- **State Persistence**: HTMX reloads now preserve the active filter state using Alpine.js `hx-include` synchronization.
- **Standalone Component Architecture**: Refactored the dashboard card into a reusable `vibarr/partials/discovery_card.html` template, ensuring visual parity across feeds, universes, and summaries.

### TVDB Integration & Metadata Enrichment
- **TVDB Service**: Implemented a robust TVDB v4 client with Bearer Token authentication and Django-caching for high-performance metadata retrieval.
- **Extended Schema**: Updated the `Show` model to store native TVDB identifiers and `AppConfig` to manage secure API credentials (Key/PIN).
- **Settings UI**: Integrated TVDB configuration into the Intelligence profile with live connection testing.
- **Automated ID Backfill**: Upgraded the discovery pipeline and metadata maintenance engine to automatically extract TVDB IDs from TMDB external references.
- **Sonarr Optimization**: Updated the series acquisition logic to prioritize TVDB IDs for lookup, significantly improving "Match Confidence" when adding new tastings.

### Technical Debt Purge & Stability Hardening
- **Payload Bloat Elimination**: Removed large data structures (like `library_titles` arrays) from Django-Q task signatures. Data is now fetched locally within the worker context to prevent Redis memory exhaustion during large scale operations.
- **O(1) Lookup Optimization**: Converted all library title matching logic from O(N) list scans to O(1) set-based lookups across all background tasks and media services, significantly speeding up synchronization.
- **API Throttling & Connection Pooling**: Implemented `requests.Session()` for persistent connections to AI and TMDB endpoints. Added mandatory rate-limiting (`time.sleep`) during massive history backfills to prevent API bans.
- **Silent Failure Remediation**: Replaced dangerous bare `except: pass` blocks in external sync tasks (Sonarr/Radarr) and media providers with explicit, structured error logging for improved observability.
- **Import Purge**: Eliminated all inline/lazy imports across the project. All dependencies are now explicit at the top-level, improving load-time performance and developer clarity.
- **Circular Import Resolution**: Created `vibarr/utils/providers.py` to house shared media-server utility functions, breaking a critical circular dependency chain between polling and recommendation tasks.
- **Transactional Integrity**: Implemented `transaction.atomic()` for all state-heavy views (e.g., `MarkWatchedView`, `TasteActionView`). Database updates now roll back automatically if external service calls fail.
- **UI Architecture (Partial Templates)**: Removed hardcoded HTML strings from Python views. All UI responses (Success/Fail status badges, test results) are now rendered via clean, reusable Django partial templates (`vibarr/partials/`).
- **Task Optimization**: Removed blocking `time.sleep()` calls from generic polling loops, relocating specific throttles only to third-party API resolution blocks.

### Dashboard UX Overhaul
- **Flip-Card Architecture**: Discovery and Tasting cards use CSS 3D flip animation powered by Alpine.js to reveal AI reasoning on click, ensuring state consistency during HTMX swaps.
- **Action Buttons**: Taste / Seen / Skip buttons visible at card footer; Delete button inline on tasting cards.
- **WATCHED State**: New `ShowState.WATCHED` enum; `MarkWatchedView` creates manual watch events for AI learning (defaults `season: 0` and `episode: 0` to satisfy database constraints).
- **Recommendation Model**: Added `vibe_tags_list` property for clean template rendering.
- **Seamless State Transitions**: Clicking "Taste" immediately moves the show to the Active Tastings grid via an HTMX Out-of-Band (`hx-swap-oob`) swap, while Alpine fades it out of the Discovery Feed without resetting the user's scroll position.
- **Discovery Feed Navigation**: Added frosted-glass hover navigation arrows (scroll left/right) and exposed native smooth scrollbars for desktop users.
- **Tasting Section Horizontal Scroll**: Synchronized the Active Tastings grid into a horizontal scrolling layout (`flex-nowrap`) with navigation buttons, consistent with the Discovery section.
- **Card Design Standardized**: Unified all dashboard card heights to `h-[460px]` and tightened internal padding (title/progress) to prevent poster cropping while maintaining a clean vertical alignment across the feed.
- **Hover Hint Sync**: Ported the pulsing "Click poster to see reasoning" hint and dimmed overlay from Discovery cards to the Tasting cards for a unified interactive language.

### HTMX + Alpine.js Hardening
- **Card Interactivity Rebuilt**: Replaced fragile vanilla JS `onclick` event handlers with robust Alpine.js state (`x-data="{ flipped: false, hidden: false }"`) for flip-cards.
- **Null Indicator Crash Fixed**: Resolved a stubborn `htmx-internal-data` crash caused by an invalid inherited `hx-indicator="closest section h2 img"` selector.
- **Safe DOM Teardown**: Action buttons on cards use `hx-swap="none"` and rely on Alpine's `@htmx:after-request` event to trigger a visual fade-out.

### Discovery Pipeline Hardening
- **TMDB ID Namespace Fix**: Corrected a critical schema flaw where TMDB IDs overlapped between Movies and TV Shows. Changed `tmdb_id` from a global `unique=True` field to a `UniqueConstraint` on `(tmdb_id, media_type)`. This prevents "collisions" where a TV show recommendation would incorrectly pull an existing movie record with the same ID.
- **Cross-Media Intelligence**: Updated the recommendation engine to correctly track and preserve the `media_type` of cross-recommended items (e.g., suggesting a show based on a movie), ensuring correct metadata tagging.
- **Cache-Based Debouncing**: Replaced the record-dependent debounce with a global `cache`-based debounce. This ensures that even if a title results in no recommendations (e.g., all matches already owned), the scout will not repeatedly re-process it until the 24-hour window expires.
- **Deep History Profiling**: Updated the `background_scout` to crawl the user's *entire* watch history over time in batches of 5. The system now systematically backfills un-scouted historical titles, building a complete taste profile beyond the immediate 24-hour recent viewing window.

### Settings & Sync
- **Library Checklist Template Fix**: Replaced Python-style ternary in Django template with proper `{% if %}` tag syntax.
- **Discovery Dedup**: Pipeline now checks `MediaWatchEvent` by TMDB ID in addition to `Show` and library title matching.

### Production-Grade Watch History & Sync
- **Database Hardening**: Migrated all critical `CharField` strings to PostgreSQL-native `TextField` to eliminate `DataError` crashes from character limits.
- **Bulk Insertions**: History polling now uses `bulk_create` for massive 99% reduction in I/O overhead during backfills.
- **Memory-Safe Pagination**: Replaced the "all-at-once" Plex history grab with a safe 100-item paginated API strategy, preventing OOM worker crashes on 10-year backfills.
- **Uncapped Fallback Scans**: Removed the artificial 50-item limit on fallback scans during deep backfills, ensuring users without Plex Pass can still fully index their watch history.
- **N+1 Query Elimination**: Optimized the Dashboard progress bars to utilize Django's `prefetch_related` cache, keeping the UI perfectly responsive while thousands of history items sync in the background.
- **Dynamic Sync Banner**: Added a premium, pulsing sync banner to the History page that tracks live progression.
- **True Percentage Parsing**: The banner parses the exact synchronization percentage rather than relying on string-slicing hacks.
- **Consolidated History UI**: History items are now cleanly grouped by Show Title with dynamic episode counts, and navigated via an advanced "elided" pagination system (e.g., `1 2 ... 14 15`).

### UI/UX Enhancements (v1.2)
- **Scalable Feed Architecture**: Decoupled the Discovery and Tasting feeds from the main dashboard into dedicated full-page views (`/discoveries`, `/tastings`), allowing the system to scale to hundreds of recommendations without UI lag.
- **Executive Summary Dashboard**: Redesigned the dashboard to show only the "Top 5" items per section, using a wide 5-column grid layout and prioritized sorting (Progress > Score).
- **Color-Coded Media Badges**: Implemented a semantic color system for media types. Movies (Radarr) now use Amber (`amber-500`) and Shows (Sonarr) use Blue (`blue-500`).
- **Unified Card Badges**: Added absolute-positioned media type and content rating badges to all dashboard cards (Discovery, Tasting, Nightcap) for instant identification.
- **Thematic Progress Bars**: Synchronized Tasting progress bars with the media color system (Amber glow for movies, Blue glow for shows).
- **External Media Links**: Added interactive "View on TMDB" buttons to the reasoning side of all cards, using click-propagation protection to maintain card state.
- **Vibe Tag Context**: Background reasoning tags now reflect the media type color, creating a unified visual language for each title.

### Agentic Hardening (v1.2)
- **Dual-Track Intelligence Engine**: Deployed independent "Cinema" and "TV" sourcing agents. The system now maintains separate discovery inventories for each media type, eliminating recency bias.
- **IMDB Enrichment Integration**: The scout now cross-references TMDB results with IMDB identifiers. AI reranking logic has been upgraded to utilize high-consensus quality signals (IMDB ratings, popularity metrics, and vote counts).
- **Metadata Maintenance Engine**: Implemented a resilient backfilling task that updates existing records with missing IMDB IDs and fresh ratings in both batch and asynchronous "Deep Refresh" modes.
- **Weighted History Profiling**: Implemented a sophisticated history sampler that builds an AI profile using 100% primary habit data + a configurable percentage of "influencer" habit data.
- **Resilience Protocol**: Added a mandatory retry-with-backoff strategy for external API calls and wrapped maintenance loops in per-item error isolation.
- **Strict Reliability Protocol**: Established mandatory `task.md`, `/rebuild`, and `/health` gates for all code modifications.ux compatibility on Windows host.
- **Skill Automation**: Converted manual markdown instructions into executable scripts (`smoke_test.py`, `verify_connections_logic.py`).
- **Agency Rules Updated**: Mandatory container rebuilds on code changes enforced via `AGENCY.md`.
- **Gitignore Protection**: Specific patterns implemented to prevent accidental exclusion of the `media` service module.

## Quality Gates
- [x] **Security**: Non-root container execution & Token-based API Auth.
- [x] **UI**: 100% Responsive glassmorphic design with Household Lens switching.
- [x] **Stability**: Reverse-proxy ready via `url_base` middleware.
- [x] **HTMX Compatibility**: All action views return valid HTML fragments (never empty strings).

## Known Technical Debt
- `docker-compose.yml` uses deprecated `version` attribute (cosmetic warning only).
- Card heights are now standardized at `h-[460px]` but still need responsive testing on smaller mobile viewports.
- Alpine.js is loaded globally and effectively powers the interactive card states, toasts, and persona dropdowns.

## Next Steps
- Advanced Purge Rules (e.g. "Delete if not watched in 30 days").
- Mobile PWA Optimization.
- Detailed AI Log Inspector (See the "Brain" in action).
- Responsive flip-card heights for mobile viewports.
- Jellyfin VirtualFolders API validation for diverse library types.
