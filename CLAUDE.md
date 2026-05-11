# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

PM MVP: a single-container Kanban app with an AI assistant. NextJS frontend + FastAPI backend + SQLite + OpenRouter (`openai/gpt-oss-120b`). MVP scope and locked decisions live in [AGENTS.md](AGENTS.md) and [docs/PLAN.md](docs/PLAN.md). Per-directory `AGENTS.md` files (backend, frontend, scripts) describe the current state of each area — read them before making changes there.

## Coding standards (from AGENTS.md, non-negotiable)

1. Use latest library versions and idiomatic approaches.
2. Keep it simple. Do not over-engineer, no unnecessary defensive programming, no extra features beyond what's asked.
3. Be concise. Keep docs minimal. **Never use emojis.**
4. When debugging, identify root cause with evidence before fixing — do not guess.

## Run / build

Production-style run is via Docker (single container, port 8000):

```bash
./scripts/start-mac.sh        # macOS
./scripts/stop-mac.sh
./scripts/start-linux.sh      # Linux
./scripts/start-windows.ps1   # Windows PowerShell
```

Start scripts build image `pm-mvp`, run container `pm-mvp`, and pass `.env` from repo root via `--env-file` if present. The `.env` must contain `OPENROUTER_API_KEY` for AI features.

Local backend dev (without Docker) uses `uv`:

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

Local frontend dev (standalone, no backend integration):

```bash
cd frontend
npm install
npm run dev
```

## Tests

Backend (pytest, run from `backend/`):

```bash
uv run pytest                                  # all
uv run pytest tests/test_board_api.py          # one file
uv run pytest tests/test_ai_chat.py::test_name # one test
```

Frontend (run from `frontend/`):

```bash
npm run test:unit       # vitest
npm run test:e2e        # playwright
npm run test:all        # unit then e2e
npm run lint
```

## Architecture

**Single-process deploy.** The Dockerfile multi-stage-builds the Next.js frontend (`next build` with static export to `frontend/out/`), then copies the output into the Python image at `backend/app/static/`. FastAPI serves the static assets from `/` and exposes the API under `/api/*`. There is no separate frontend server in production.

**Auth gating happens at the root route.** `GET /` in [backend/app/main.py](backend/app/main.py) returns either an inline HTML login page (when no session cookie) or the built Next.js `index.html` (when authenticated). Login is a hardcoded `user`/`password` check that sets a session cookie. All `/api/*` routes (except auth) require the session cookie. Cookie security is controlled by `PM_COOKIE_SECURE` env var.

**Persistence layer.** SQLite at `backend/data/pm.db`. [backend/app/db.py](backend/app/db.py) handles schema init, idempotent seeding, and all board mutations (column rename, card CRUD, move). Schema is documented in [docs/DB_SCHEMA.md](docs/DB_SCHEMA.md): normalized `users` / `boards` / `columns` / `cards` tables with `meta_json` / `settings_json` fields for optional metadata only. One board per user is DB-enforced (`UNIQUE(user_id)` on `boards`). DB is auto-created and seeded on first startup — no migration tooling.

**AI flow.** [backend/app/ai.py](backend/app/ai.py) is the OpenRouter client (`POST /api/ai/smoke` is the connectivity probe). [backend/app/ai_chat.py](backend/app/ai_chat.py) implements `POST /api/ai/chat`: it sends the current board JSON + user message + per-user in-memory conversation history (`CONVERSATION_HISTORY` dict in `main.py`, keyed by user id — **not persisted, lost on restart by design**) and expects a structured response with a reply text and an optional board mutation payload. Validated mutations are applied through the same `db.py` helpers used by the REST API; invalid/partial outputs are rejected without mutating state.

**Frontend integration.** The Next.js app (`frontend/src/`) is App Router + React 19 + Tailwind v4 + `@dnd-kit` for drag-and-drop. Board state lives in `KanbanBoard.tsx`; core types, move logic, and ID helpers in `src/lib/kanban.ts`. The frontend calls backend APIs for persistence and the AI sidebar; it falls back to in-memory state only when the backend is unreachable.

## Conventions worth knowing

- Python deps are managed by `uv` (not pip). Use `uv run <cmd>` and `uv sync` — do not invent a virtualenv.
- Backend route handlers live directly in `app/main.py`; do not introduce a routers/ split unless asked.
- `meta_json` / `settings_json` are for optional metadata only — do not move normalized fields into JSON.
- Conversation history is intentionally in-memory for MVP. Do not add persistence without a request.
- The plan in [docs/PLAN.md](docs/PLAN.md) is the source of truth for phased work and "Locked Decisions". Reread it before scope changes.
