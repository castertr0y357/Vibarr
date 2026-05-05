# Project Status: Vibarr

## Current State: HEADLESS & HOUSEHOLD READY (v1.0-RC1)
**Last Checkpoint**: 2026-05-05 (API-First & Household Lenses)

## Core Architecture
- **Framework**: Django (Postgres + Redis + Django-Q2)
- **API Strategy**: Headless Hybrid (Django CBVs + APIMixin supporting JSON & HTMX)
- **Deployment**: Hardened Docker (Multi-stage build, Non-root user, isolated networking)
- **Integrations**: Plex/Jellyfin (Syncing), Sonarr/Radarr (Automation), TMDB, OpenAI-Compatible AI (Ollama/Remote)
- **Frontend**: Vanilla CSS + HTMX (Real-time polling and partial updates)

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
- [x] **Setup Wizard**: Automated first-run calibration.
- [x] **The Nightcap**: Time-of-day mood selector with AI-reranking.
- [x] **Concierge Notifications**: Discord/Telegram triggers.
- [x] **Semantic Vibe Search**: Natural language discovery via AI.
- [x] **Universe Architect**: AI-driven cinematic universe detection.
- [~] **Insights Engine**: (Removed/Distilled to keep app lean).

## Quality Gates
- **Security**: Non-root container execution & Token-based API Auth.
- **UI**: 100% Responsive glassmorphic design with Household Lens switching.
- **Stability**: Reverse-proxy ready via `url_base` middleware.

## Next Steps
- Advanced Purge Rules (e.g. "Delete if not watched in 30 days").
- Mobile PWA Optimization.
- Detailed AI Log Inspector (See the "Brain" in action).
