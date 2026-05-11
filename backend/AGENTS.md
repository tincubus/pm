## Backend Overview

This directory now contains the FastAPI backend for the PM MVP.

### Current files

- `pyproject.toml`: Python project config and dependencies (managed with `uv`).
- `app/main.py`: FastAPI application entrypoint.
  - `GET /`: auth-gated frontend route. Shows login page when signed out, static Kanban app when signed in.
  - `GET /api/health`: basic health endpoint.
  - `GET /api/hello`: sample API endpoint.
  - `POST /api/auth/register`: creates a new user with email + password (min 8 chars) and sets session cookie.
  - `POST /api/auth/login`: accepts email + password, sets session cookie. Generic error for invalid credentials.
  - `POST /api/auth/logout`: clears session cookie.
  - `GET /logout`: clears session and redirects to `/`.
  - `GET /api/auth/session`: reports current auth state. Refreshes session expiry as a side effect.
- `app/db.py`: SQLite schema/init/seed logic and board mutation helpers.
- `GET /api/board`: returns the authenticated user's board.
- `PATCH /api/columns/{column_id}`: renames a column.
- `POST /api/columns/{column_id}/cards`: creates a card in a column.
- `PATCH /api/cards/{card_id}`: edits a card title/details.
- `POST /api/cards/{card_id}/move`: moves a card across/in columns.
- `DELETE /api/cards/{card_id}`: deletes a card.
- `POST /api/ai/smoke`: authenticated OpenRouter connectivity smoke test (`2+2`).
- `POST /api/ai/chat`: board-aware structured AI response endpoint with optional board updates.
- `app/__init__.py`: package marker for app module imports.
- `app/static/`: runtime static asset directory copied from frontend build inside Docker.
- `tests/test_auth.py`: backend auth/session behavior tests.
- `tests/test_board_api.py`: backend board read/mutation and DB-creation tests.
- `tests/test_ai_smoke.py`: backend AI smoke endpoint tests with mocking.
- `tests/test_ai_chat.py`: structured-output parsing, conversation history, and mutation application tests.

### Current scope

All MVP parts 2-10 are implemented. Backend covers scaffolding, static frontend serving, login/session gating, board CRUD APIs, OpenRouter connectivity, and structured AI chat with transactional board mutations via `db.apply_ai_board_update`.