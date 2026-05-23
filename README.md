# 🌌 Vibarr: The Autonomous Talent Scout for your Media Lab

**Vibarr** is a production-grade, AI-driven media discovery and automation engine designed to transform your home lab into an intelligent "Media Lab." It doesn't just suggest content; it proactively manages your library through a sophisticated lifecycle of discovery, automated "tasting," and permanent commitment.

![Dashboard Preview](https://via.placeholder.com/1200x600/1a1a1a/E94560?text=Vibarr+v1.8+Dashboard)

## 🍷 The Vibarr Lifecycle: Discovery → Tasting → Commitment

Vibarr operates on a unique "Talent Scout" metaphor, moving beyond passive watchlists to an active, autonomous pipeline:

1.  **Discovery (The Scout)**: Vibarr's dual-track intelligence (AI + Weighted Heuristics) scans your history and the broader cinematic universe to find your next obsession.
2.  **Tasting (The Trial)**: High-confidence matches are automatically "tasted." Vibarr triggers your automation tools (Sonarr/Radarr) to grab a 3-episode trial. These appear on your dashboard as "Active Tastings."
3.  **Commitment (The Graduation)**: If you watch the episodes on Plex or Jellyfin, Vibarr "commits" the series, promoting it to your permanent library. If the vibe isn't right and you ignore it, Vibarr automatically purges the files to keep your storage lean.

---

## ✨ Core Features (v1.8)

### 🧠 Dual-Track Intelligence
*   **4+1 Serendipity**: An AI ranking system that provides 4 high-confidence matches and 1 "Wildcard" thematic connection to broaden your horizons.
*   **Weighted Heuristic Engine**: A tunable non-AI recommendation system using metadata signals like Ratings, Popularity, Genres, Keywords, and Collections.
*   **Autonomous Scout**: High-confidence matches (>9.5) bypass the suggestion phase and trigger automatic tastings immediately.

### 🪐 Universe Architect
*   **Franchise Detection**: Automatically identifies cinematic universes (MCU, Star Wars, DCU, etc.) across your library.
*   **Collection Mirroring**: Synchronizes these universes directly to your media server as Plex Collections or Jellyfin BoxSets.
*   **Complete Collection**: One-click logic to identify and "taste" missing members of a franchise to complete your sets.

### ⚡ Vibe Snap
*   **Contextual Discovery**: A mood-based quick search integrated into the search page. It's time-of-day aware—suggesting "Morning Coffee" vibes at 8 AM and "Gritty Noir" at midnight.
*   **Semantic Vibe Search**: Natural language discovery. Search for *"Gritty 90s cyber-noir with a slow burn"* instead of just genres.

### 👓 Household Lenses
*   **Persona Filtering**: Real-time dashboard filters for "Adult", "Family", and "Kids" personas.
*   **Safety Enforcement**: Automatic rating and genre blacklisting based on the active lens.

### 🛠 Automation & Integrations
*   **Manager-Aware Library Sync**: Cross-references Plex/Jellyfin with Radarr/Sonarr to identify owned content before it even hits the server.
*   **Seerr-Aware Sourcing**: Native integration with Overseerr/Jellyseerr request history to inform recommendations.
*   **Concierge Notifications**: Real-time Discord or Telegram alerts for tastings, purges, and universe discoveries.

---

## 🚀 Quick Start

### 1. Prerequisites
- **Media Server**: Plex or Jellyfin
- **Automation**: Sonarr and/or Radarr
- **Metadata**: TMDB API Key (TVDB v4 optional)
- **Intelligence**: OpenAI-compatible API (OpenAI, Ollama, etc.)

### 2. Deployment (Docker)
Vibarr is designed to run in a hardened Docker environment.
```bash
docker-compose up -d
```

### 3. Setup Wizard
Visit `http://localhost:8282` to start the interactive 5-step Setup Wizard. Vibarr will guide you through connecting your services and initializing your first library scan.

---

## 🛠 Technical Stack
*   **Backend**: Django (Postgres + Redis + Django-Q2)
*   **Frontend**: Vanilla CSS (Glassmorphism) + HTMX + Alpine.js
*   **Architecture**: Modular Monolith with strictly decoupled background tasks.
*   **API**: Headless Hybrid (APIMixin supporting JSON & HTMX fragments).

---

## 🌍 International Support
Vibarr supports localized metadata and content ratings. Configure your **TMDB Region** and **Language** in settings to get "Where to Watch" availability and localized ratings (UK, CA, AU, etc.).

---
*Built with ❤️ for the home lab community.*

## 🔍 Troubleshooting

### 1. CSRF 403 Errors behind a Reverse Proxy
If you host Vibarr on an external server behind an SSL-terminating reverse proxy (like Nginx, Caddy, Traefik, or Cloudflare Tunnel) and encounter a `403 Forbidden` error on POST/HTMX requests:
* **Configure Trusted Origins**: Set `CSRF_TRUSTED_ORIGINS` in your `.env` file to the exact scheme and domain you use to access the app (e.g., `CSRF_TRUSTED_ORIGINS=https://vibarr.your-domain.com`).
* **Secure Cookies**: If using HTTPS, turn on secure cookies by setting `CSRF_COOKIE_SECURE=True` and `SESSION_COOKIE_SECURE=True` in your `.env`.
* **SSL Headers**: Ensure your proxy passes the `X-Forwarded-Proto` header. Vibarr is pre-configured to detect SSL termination via `SECURE_PROXY_SSL_HEADER`.

### 2. AI Recommendations with Open WebUI
If you configure Open WebUI as your OpenAI-compatible AI backend:
* **Correct API Endpoint**: Use the full completions path containing the `/api` prefix:
  * `https://your-open-webui-url.com/api/v1/chat/completions`
  * Or `https://your-open-webui-url.com/api/chat/completions`
  * *Note: Accessing `/v1/chat/completions` directly without `/api` will result in a `405 Method Not Allowed`.*
* **Open WebUI 400 Bad Request**: Older versions of Open WebUI crash with `400 Bad Request` if a `chat_id` parameter is not present. Vibarr automatically appends a dummy `"chat_id": ""` to all outbound AI payloads to avoid this issue.

---

## 📜 License
This project is licensed under the **GNU Affero General Public License v3 (AGPLv3)**. See the [LICENSE](LICENSE) file for details.

