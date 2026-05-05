# 🌌 Vibarr: The Autonomous Talent Scout for your Media Lab

Vibarr is a next-generation media discovery and automation engine. It doesn't just suggest things to watch—it proactively manages your library, "tastes" new shows for you, architects cinematic universes, and keeps you updated via a personal concierge.

![Dashboard Preview](https://via.placeholder.com/1200x600/1a1a1a/E94560?text=Vibarr+Dashboard+Preview)

## ✨ Core Features

*   **🧠 Semantic Vibe Search**: Search for movies and shows using natural language vibes like *"Gritty 90s cyber-noir with a slow burn"* or *"Comforting Sunday morning animation."*
*   **🍷 Dynamic Tasting**: Vibarr automatically downloads the first 3 episodes of a show it thinks you'll like. If you watch them, it commits the full series. If you don't, it purges them to save space.
*   **🌙 The Nightcap**: A contextual mood picker that adapts to your time of day. Get "Morning Coffee" vibes at 8 AM and "Gritty Noir" at midnight.
*   **🪐 Universe Architect**: Automatically detects cinematic universes (MCU, Star Wars, DCU) and organizes them into collections on your media server.
*   **🔔 Concierge Notifications**: Real-time alerts via Discord or Telegram when a tasting is ready, a show is purged, or a new universe is found.
*   **📊 Insights Engine**: A stunning "Year in Review" dashboard analyzing your watch history and library health.

## 🚀 Quick Start

### 1. Prerequisite
- **Plex** or **Jellyfin**
- **Sonarr** and/or **Radarr**
- **TMDB API Key**
- **Ollama** (for local AI) or an **OpenAI API Key**

### 2. Deployment (Docker)
```bash
docker-compose up -d
```

### 3. Setup Wizard
Once running, visit `http://localhost:8000`. Vibarr will automatically detect it's unconfigured and lead you through a 5-step interactive setup wizard to connect your services.

## 🌍 International Support
Vibarr is built for the global community. You can configure your **TMDB Region** and **Language** in settings to ensure:
- Localized content ratings (UK, CA, AU, etc.)
- "Where to Watch" streaming availability specific to your country.
- Translated metadata.

## 🛠 Tech Stack
- **Backend**: Django, Django-Q2, Redis, Postgres
- **Frontend**: Vanilla CSS (Glassmorphism), HTMX
- **Intelligence**: LLM (Llama 3 / Gemma / GPT-4), TMDB API

---
*Built with ❤️ for the home lab community.*
