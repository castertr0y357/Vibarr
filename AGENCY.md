# Agent Rules of Engagement (AGENCY.md)

This document defines how Antigravity (AI) and the User collaborate on this project.

## Agent Behaviors
0. **Session Restoration**: I will always read `status.md` and `task.md` at the start of a session to restore state without redundant file scans.
1. **Status Maintenance**: I will update `status.md` at the end of every significant task or feature implementation.
2. **Proactive Health Checks**: I will run `verify_connections.md` whenever the `.env` or API services change.
3. **Context Awareness**: I will monitor the length of the session and suggest a `session_handover.md` if I detect performance degradation.

## Command Triggers
- `/handover`: Immediately run `skill_session_handover.md`. Stop current work and prepare for session refresh.
- `/health`: Immediately run `skill_pre_flight_check.md` and `skill_api_smoke_test.md`.
- `/logs`: Immediately run `skill_log_forensics.md` and provide a summary of the latest errors.
- `/sync`: Immediately run `skill_manual_sync_cycle.md`.
- `/rebuild`: Immediately run `skill_rebuild_stack.md`.

## CI/CD Workflow
- **Development**: Work happens on local branches.
- **Quality Gate (MANDATORY)**: Before declaring any task "complete," I MUST run:
    1. **Trigger: Code Change**: If any `*.py`, `Dockerfile`, or `docker-compose.yml` was modified, I MUST run `skill_rebuild_stack.md`.
    2. **Verification**: Run `skill_pre_flight_check.md` to ensure migrations and system health.
    3. **UI Validation**: Run `skill_api_smoke_test.md` to ensure no 500 errors.
- **Auto-Fix**: If `pre_flight_check` fails due to unapplied migrations, I will attempt to fix them via `python manage.py migrate` before escalating.
- **Documentation**: Any change to API interaction must be reflected in the relevant `skill_*.md`.

## Quality Standard
- All UI changes must adhere to the "Rich Aesthetics" guide (Glassmorphism, Dark Mode, Responsive).
- Backend logic must be asynchronous (Django-Q) to prevent UI blocking.
