# Project Status: Vibarr

## Current State: SONARR/RADARR HARDENING & MAINTENANCE UI (v1.9.4)
**Last Checkpoint**: 2026-05-09 (Multi-Level Monitoring Sync, Real-time Download Badges & Maintenance Actions)

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
- [x] **Sonarr/Radarr Monitoring Hardening**: Resolved a critical bug where shows were added in an unmonitored state; now ensures Series and Season 1 are active immediately.
- [x] **Multi-Level Monitoring Sync**: Enhanced the background sync to verify and "heal" monitoring status at the Series, Season, and Episode levels simultaneously.
- [x] **Real-time Download Status**: Integrated manager queues into the dashboard to display pulsing "Downloading" badges for active content.
- [x] **Heal Managers Quick Action**: Added a one-click maintenance button in the sidebar and automation settings to force-sync manager states on demand.
- [x] **Targeted Tasting Search**: Implemented granular `EpisodeSearch` commands specifically for tasting episodes, preventing bandwidth waste.
- [x] **Neon V Pulse Branding**: Implemented a unified brand identity with a custom neon-pulse logotype and favicon.
- [x] **CSS Screen Blending**: Used professional blending techniques to integrate neon assets seamlessly into the dark-mode UI without visible background boxes.
- [x] **N+1 Query Elimination**: Massively optimized background tasks by replacing loop-based existence checks with bulk pre-fetches.
- [x] **Background Task Efficiency**: Refactored history profiling and scouting to use memory-efficient aggregation and sampling, preventing bloat as libraries grow.
- [x] **Robust AI JSON Parsing**: Specialized extraction logic to handle Markdown fences, conversational prefixes, and truncated model outputs.
- [x] **Intelligence Maintenance Toasts**: Real-time visual feedback when triggering score re-evaluations or discovery scouts.
- [x] **Global Settings Context**: Application configuration is now globally available to all templates via a dedicated context processor.
- [x] **Dynamic Sidebar Control**: The 'Universes' link and 'Architect' tools now correctly hide/show based on user settings.
- [x] **Section-Isolated Settings**: Saving one settings section (e.g. Servers) no longer wipes out others (e.g. Automation).
- [x] **Reliable Plex Auth**: Reverted to standard PIN flow and stable client identifiers for maximum compatibility.
- [x] **Auto-Scan Libraries**: Selecting a media server now instantly triggers a library visibility scan.
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
- [x] **Integrated Authentication**: Three-tier enforcement (None, External, Always) with IP-aware bypassing for local networks.
- [x] **Dynamic Episode Tasting**: Intelligent "trial" counts calculated as a percentage (default 20%) of a series' first-season episode count.
- [x] **Security Dashboard**: Dedicated UI for managing access modes, password hashing, and API keys.
- [x] **Premium Login Flow**: Cinematic, glassmorphic login screen with secure session management.
- [x] **Setup Wizard Bypassing**: Added "Skip for now" logic and persistence to prevent setup loops for existing users.
- [x] **Logout Integration**: Global session termination accessible via the settings sidebar.
- [x] **Executive Prefetching**: Optimized dashboard and gallery views with pre-fetched related data to eliminate N+1 UI delays.
- [x] **Shared Library State**: Discovery tracks now share a unified library state to reduce redundant media server API calls during background scouts.
- [x] **Aggregated History Profiling**: AI-profile generation now uses optimized database-level aggregation for 10x faster habit analysis.

### Sonarr/Radarr Hardening & Maintenance UI (v1.9.4)
- **Monitoring Reliability**:
    - **Multi-Level Healing**: Refactored `sync_external_states` to check not just series-level monitoring, but also season-level (Season 1) and episode-level flags. This ensures Sonarr doesn't sit idle on a monitored show with unmonitored seasons.
    - **Add-Time Monitoring**: Hardened the `add_series` workflow to explicitly monitor Season 1 during the initial API call, eliminating "ghost" shows that Sonarr would otherwise ignore.
- **UI & Observability**:
    - **Pulsing Download Badges**: Added real-time "Downloading" indicators to the dashboard cards. These are driven by efficient bulk-queue fetches (`get_full_queue`) from the managers.
    - **Heal Managers Tool**: Created a dedicated `ExternalSyncView` and added it to the sidebar's "Quick Actions" and Automation settings.
- **Task Optimization**:
    - **Bulk Queue Matching**: Replaced per-show queue API calls with a single bulk fetch on the dashboard, significantly improving page load times when multiple tastings are active.

### Operational Hardening & Brand Identity (v1.9.3)
- **Scale & Performance Hardening**:
    - **N+1 Query Elimination**: Refactored `poll_provider_history` and `revaluate_all_recommendations` to use bulk queries and prefetched caches, ensuring O(1) database hit counts regardless of task size.
    - **Memory Optimization**: Updated `background_scout` to sample history rather than loading entire watch records, protecting system memory for users with 10k+ history events.
    - **Aggregated Profiling**: Transitioned `get_weighted_history_profile` to use `Max` and `values()` aggregation for significantly more efficient unique-title discovery.
- **Brand Identity & UI Aesthetics**:
    - **"Neon V Pulse" System**: Designed and implemented a high-contrast brand symbol used as a favicon and the lead character in the logotype.
    - **Logo Over-sizing**: Implemented a "Hero" scaling strategy for branding, making the symbol significantly larger and more detailed than the accompanying text.
    - **Holographic Integration**: Used `mix-blend-screen` CSS properties to allow neon assets with black backgrounds to float natively on the app's radial gradients.
- **Maintenance & Health**:
    - **Headless collectstatic**: Automated static asset deployment within the Docker environment using non-interactive flags.
    - **Static Serving Hardening**: Enabled explicit static routing in `urls.py` when `DEBUG` is on to support Gunicorn-based development environments.

### AI & Settings Intelligence Hardening (v1.9.2)
- **Robust AI Response Parsing**: Refactored the core AI parsing logic to survive messy model outputs, including Markdown code fences, conversational prefixes, and truncated JSON blocks.
- **Task & Batch Optimization**:
    - Reduced AI re-evaluation batch sizes to prevent token overflow.
    - Implemented string truncation for candidate overviews to stay within context windows.
    - Increased `django-q` cluster timeouts and individual API request timeouts to 300s to support complex AI reasoning.
- **Settings Architecture**:
    - **Persistence Fix**: Aligned the backend `SECTION_FIELDS` mapping with the UI templates to prevent data loss (specifically fixed the TMDB/TVDB key persistence issue).
    - **Global Context Processor**: Centralized the `AppConfig` singleton into a global template context processor, ensuring settings are consistently available across the entire UI.
- **UI & Feedback Polish**:
    - **Multi-Type Toasts**: Implemented a color-coded toast notification system for success and error states.
    - **Maintenance Confirmation**: Added immediate toast feedback when triggering manual intelligence or metadata tasks.
    - **Sidebar Visibility**: Connected the 'Universes' link and quick actions to the `universe_page_enabled` setting.
    - **Feature Completion**: Added missing Tautulli and Notification fields to the General settings page.

### Stability & Authentication Refinement (v1.9.1)
- **Plex Authentication Reverted**: Reverted to a simpler, more compatible Plex authentication flow. Uses a stable client identifier and standard PIN requirements.
- **Section-Scoped Settings Persistence**: Refactored settings update logic to prevent cross-section data loss.
- **Library Discovery Hardening**: Auto-triggering and improved fallbacks for Plex/Jellyfin library scans.

### Integrated Security & Dynamic Tasting (v1.9.0)
- **Three-Tier Authentication**: Implemented `NONE`, `EXTERNAL`, and `ALWAYS` modes.
- **Dynamic Tasting Logic**: Percentage-based trial sizes (e.g., 20% of first season).

### UX Refinement & Search Integration (v1.8.0)
- **README Overhaul**: Emphasized the "Autonomous Talent Scout" lifecycle.
- **Manual Intelligence Maintenance**: UI triggers for Score Re-evaluation and Discovery Scouting.

## Known Technical Debt
- `docker-compose.yml` uses deprecated `version` attribute (cosmetic warning only).
- Responsive testing needed for massively oversized logos on mobile viewports.
- Static serving in `urls.py` is a temporary fix for `DEBUG=True`; `whitenoise` should be implemented for true production.

## Next Steps
- **Advanced Purge Rules**: Implement "Delete if not watched in X days" or "Low Vibe Auto-Purge" logic.
- **Detailed AI Log Inspector**: Build a UI to "See the Brain" - visualizing the AI's candidate scoring and reasoning in real-time.
- **PWA / Mobile Polish**: Optimize the dashboard for "Pinned to Home Screen" usage.
- **Whitenoise Integration**: Move to a more robust static file serving model.
