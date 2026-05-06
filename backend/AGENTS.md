## Backend Overview

This directory now contains the FastAPI backend for the PM MVP.

### Current files

- `pyproject.toml`: Python project config and dependencies (managed with `uv`).
- `app/main.py`: FastAPI application entrypoint.
  - `GET /`: auth-gated frontend route. Shows login page when signed out, static Kanban app when signed in.
  - `GET /api/health`: basic health endpoint.
  - `GET /api/hello`: sample API endpoint.
  - `POST /api/auth/login`: accepts MVP credentials and sets session cookie.
  - `POST /api/auth/logout`: clears session cookie.
  - `GET /api/auth/session`: reports current auth state.
- `app/__init__.py`: package marker for app module imports.
- `app/static/`: runtime static asset directory copied from frontend build inside Docker.
- `tests/test_auth.py`: backend auth/session behavior tests.

### Current scope

This includes Part 2 scaffolding, Part 3 static frontend serving, and Part 4 fake login/session gating. It does not yet include:

- database
- AI integration