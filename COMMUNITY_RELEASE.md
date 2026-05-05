# Community Release Checklist & Considerations

If you plan on sharing Vibarr with others, here are the key technical and UX considerations to keep in mind for varying user setups.

## 1. Environment & Setup
- **Docker vs. Native**: While Docker is recommended, some users may want to run natively. We should provide a `requirements.txt` and a `setup.py` or similar for easier native installation.
- **SQLite Fallback**: Many home lab users prefer the simplicity of SQLite. We should ensure the app remains compatible with SQLite even if Postgres is the "production" default.
- **Port Mapping**: Ensure the internal ports (8000, 6379) are easily remappable in `docker-compose.yml` to avoid conflicts with other apps.

## 2. Service Compatibility
- **Jellyfin/Emby**: Full parity with Plex features (webhooks, library syncing) is essential for non-Plex users.
- **Sonarr/Radarr Versions**: Ensure API calls are compatible with both v3 and v4 of these services.
- **Reverse Proxies**: Provide templates for Nginx/Traefik configuration, especially for handling HTMX polling over WebSockets (if we add them) or long-polling.

## 3. Privacy & Transparency
- **AI Toggling**: Users should be able to disable AI entirely (Implemented: `use_ai_recommendations` setting).
- **Data Locality**: Explicitly document that Ollama runs locally, while remote LLMs (OpenAI, Anthropic) send metadata off-site.
- **Log Scrubbing**: Ensure `.env` variables and API keys are NEVER printed to logs.

## 4. UI/UX for "Normies"
- **Setup Wizard**: A first-run wizard to configure API keys instead of requiring the Django Admin.
- **Mobile responsiveness**: Ensure the dashboard is 100% usable on a phone (HTMX is great for this).
- **Dark/Light Mode**: User preference for theme.

## 5. Documentation
- **Clear Readme**: "How to get a TMDB API Key" is the #1 question users will have.
- **Skill Documentation**: Keep the `skill_*.md` files updated as they serve as excellent developer docs for contributors.
