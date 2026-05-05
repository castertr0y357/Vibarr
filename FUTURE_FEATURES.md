# Future Features & Roadmap

This file tracks features that are planned for the future but are not currently in active development.

## Multi-User Support
- **Status**: Postponed (Save for later)
- **Goal**: Allow Vibarr to track watch history and generate recommendations for multiple Plex users, not just the primary account holder.
- **Complexity**: High (Requires mapping Plex users to Vibarr profiles and handling shared library states).

## Mobile App Wrapper
- **Goal**: A simple Capacitor/Cordova wrapper for the HTMX dashboard.

## Advanced Purge Rules
- **Goal**: Allow custom rules like "Delete if not watched within 30 days of download" or "Keep only if IMDB > 7".

## Heuristic Recommender Refinement
- **Goal**: Improve the non-AI matching logic using multi-weighted TMDB metadata (credits, keywords, collections).

## Subtitle Monitoring (Bazarr Integration)
- **Goal**: Alert users if a "tasting" show is missing subtitles in their preferred language.

## Disk Space Strategist (Value-per-Gigabyte)
- **Goal**: Analyze the entire library for "low value" content (low ratings, untouched for years) when disk space is low, and suggest purges to make room for new interests.
- **Complexity**: Medium (Requires disk space monitoring and historical watch analysis).

## Dynamic Curator (Ephemeral Home Screen)
- **Goal**: Automatically create and rotate temporary thematic collections on the Plex/Jellyfin home screen (e.g., "Neon Noir Week") to keep the library feeling fresh.
- **Complexity**: Medium (Requires API access to create/delete collections).
