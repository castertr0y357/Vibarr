# Project Status: Vibarr

## Current State: INTERACTIVE DASHBOARD (v1.1)
**Last Checkpoint**: 2026-05-06 (Dashboard UX Overhaul & HTMX/Alpine Hardening)

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

## Recent Changes (v1.1)
### Dashboard UX Overhaul
- **Flip-Card Architecture**: Discovery and Tasting cards use CSS 3D flip animation (vanilla JS, no Alpine) to reveal AI reasoning on click.
- **Action Buttons**: Taste / Seen / Skip buttons visible at card footer; Delete button inline on tasting cards.
- **WATCHED State**: New `ShowState.WATCHED` enum; `MarkWatchedView` creates manual watch events for AI learning.
- **Recommendation Model**: Added `vibe_tags_list` property for clean template rendering.

### HTMX + Alpine.js Hardening
- **Alpine/HTMX Conflict Resolved**: Removed Alpine `x-data`/`@click` from all card templates. Flip logic uses pure vanilla JS `onclick` + `classList.toggle`. This prevents Alpine from stripping HTMX's event bindings during deferred initialization.
- **Empty Response Crash Fixed**: HTMX 1.9.10 crashes on `outerHTML` swap with empty `HttpResponse("")`. All action views now return `HTMX_REMOVE` — a self-collapsing invisible `<div>` that HTMX can safely swap.
- **CSRF Token Handling**: Global `htmx:configRequest` listener reads from hidden `{% csrf_token %}` input (not cookies) for reliable cross-container auth.

### Settings & Sync
- **Library Checklist Template Fix**: Replaced Python-style ternary in Django template with proper `{% if %}` tag syntax.
- **Discovery Dedup**: Pipeline now checks `MediaWatchEvent` by TMDB ID in addition to `Show` and library title matching.

## Quality Gates
- **Security**: Non-root container execution & Token-based API Auth.
- **UI**: 100% Responsive glassmorphic design with Household Lens switching.
- **Stability**: Reverse-proxy ready via `url_base` middleware.
- **HTMX Compatibility**: All action views return valid HTML fragments (never empty strings).

## Known Technical Debt
- `docker-compose.yml` uses deprecated `version` attribute (cosmetic warning only).
- Flip-card height is fixed at `h-[420px]` — needs responsive testing on smaller screens.
- Alpine.js is still loaded globally but only used for toasts and persona dropdown; cards use vanilla JS.

## Next Steps
- Advanced Purge Rules (e.g. "Delete if not watched in 30 days").
- Mobile PWA Optimization.
- Detailed AI Log Inspector (See the "Brain" in action).
- Responsive flip-card heights for mobile viewports.
- Jellyfin VirtualFolders API validation for diverse library types.
