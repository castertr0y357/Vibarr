# Project Status: Vibarr

## Current State: HEADLESS & HOUSEHOLD READY (v1.0-RC1)
**Last Checkpoint**: 2026-05-05 (Production-Ready Settings & Automated Onboarding)

## Core Architecture
- **Framework**: Django (Postgres + Redis + Django-Q2)
- **API Strategy**: Headless Hybrid (Django CBVs + APIMixin supporting JSON & HTMX)
- **Deployment**: Hardened Docker Compose (Orchestrated Postgres, Redis, Web, and Worker)
- **Integrations**: Plex/Jellyfin (Media), Sonarr/Radarr (Automation), Overseerr/Jellyseerr (Requests), TMDB, OpenAI-Compatible AI
- **Frontend**: Vanilla CSS + HTMX + Alpine.js (Real-time polling, partial updates, dynamic states)

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

## Quality Gates
- **Security**: Non-root container execution & Token-based API Auth.
- **UI**: 100% Responsive glassmorphic design with Household Lens switching.
- **Stability**: Reverse-proxy ready via `url_base` middleware.

## Next Steps
- Advanced Purge Rules (e.g. "Delete if not watched in 30 days").
- Mobile PWA Optimization.
- Detailed AI Log Inspector (See the "Brain" in action).
