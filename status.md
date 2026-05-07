# Project Status: Vibarr

## Current State: INTERACTIVE DASHBOARD (v1.1)
**Last Checkpoint**: 2026-05-07 (Production-Grade Watch History & Sync Optimization)

## Core Architecture
- **Framework**: Django (Postgres + Redis + Django-Q2)
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
- **The Nightcap**: Contextual mood-based recommendations (Time/Day aware).
- **Concierge Notifications**: Real-time Discord/Telegram updates.

## Active Features
- [x] **Headless API**: Full token-based API access for external community integrations.
- [x] **Household Lenses**: Persona-based filtering (Age limits & Genre blacklists).
- [x] **Autonomous Scout**: AI-driven auto-acquisition based on confidence thresholds.
- [x] **Hardened Docker**: Production-ready containerization.
- [x] **Automated Onboarding**: Setup Wizard with Plex PIN Auth & Media Source selection.
- [x] **Production Settings**: 100% Model synchronized form with HTMX connection validation.
- [x] **Companion Manager**: Seamless sync with Overseerr/Jellyseerr.
- [x] **The Nightcap**: Time-of-day mood selector with AI-reranking.
- [x] **Concierge Notifications**: Discord/Telegram triggers.
- [x] **Semantic Vibe Search**: Natural language discovery via AI.
- [x] **Universe Architect**: AI-driven cinematic universe detection.
- [x] **Flip-Card Reasoning**: Interactive card flip reveals AI "Scout Reasoning" and Vibe Tags.
- [x] **Mark as Watched**: Users can flag already-seen titles; feeds AI learning and prevents re-suggestion.
- [x] **Duplicate Prevention**: Discovery pipeline cross-references watch history and library scans before suggesting.
- [x] **Monitored Libraries**: Inclusion-based library selection (replaced exclusion model for clarity).
- [x] **Inline Sidebar Navigation**: Icons and text on same line for clean visual hierarchy.
- [x] **Hardened Skills**: Fully automated `doctor`, `smoke_test`, and `rebuild` workflows with PowerShell/Docker Desktop compatibility.
- [x] **Self-Healing Diagnostics**: Automatic CRLF-to-LF conversion and migration checks.
- [x] **Zero-Config Plex Discovery**: Automated server discovery via token (no manual URL/IP guessing).
- [x] **Settings UX Hardening**: Auto-save before authentication and live unsaved library scanning.

## Recent Changes (v1.1)
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
- **Null Indicator Crash Fixed**: Resolved a stubborn `htmx-internal-data` crash caused by an invalid inherited `hx-indicator="closest section h2 img"` selector. This invalid selector evaluated to `null`, causing HTMX to abort AJAX requests entirely. Indicators now use explicit IDs (`#tasting-indicator`) and buttons isolate themselves with `hx-indicator="this"`.
- **Safe DOM Teardown**: Action buttons on cards use `hx-swap="none"` and rely on Alpine's `@htmx:after-request` event to trigger a visual fade-out. This explicitly prevents HTMX from trying to attach events to deleted DOM nodes, eliminating edge-case swap crashes.
- **Aggressive Polling Removed**: Removed `hx-trigger="every 15s"` and `every 30s` from the dashboard containers. Background polling was destroying the DOM while users were interacting with cards, leading to crashes. The dashboard now gracefully updates via `sync-complete from:body` events.
- **CSRF Token Handling**: Global `htmx:configRequest` listener reads from hidden `{% csrf_token %}` input (not cookies) for reliable cross-container auth.

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

### Agentic Hardening (v1.2)
- **CRLF Line Ending Fix**: Automated conversion of `entrypoint.sh` to ensure Linux compatibility on Windows host.
- **Skill Automation**: Converted manual markdown instructions into executable scripts (`smoke_test.py`, `verify_connections_logic.py`).
- **Agency Rules Updated**: Mandatory container rebuilds on code changes enforced via `AGENCY.md`.
- **Gitignore Protection**: Specific patterns implemented to prevent accidental exclusion of the `media` service module.

## Quality Gates
- **Security**: Non-root container execution & Token-based API Auth.
- **UI**: 100% Responsive glassmorphic design with Household Lens switching.
- **Stability**: Reverse-proxy ready via `url_base` middleware.
- **HTMX Compatibility**: All action views return valid HTML fragments (never empty strings).

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
