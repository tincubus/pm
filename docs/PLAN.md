# Project Implementation Plan

This is the execution plan for the MVP in `AGENTS.md`, with checklists, test gates, and success criteria.

## Locked Decisions

- Runtime shape: single Docker container for MVP.
- Auth UX: fake login with hardcoded credentials (`user` / `password`).
- Data model: normalized SQLite tables plus JSON field(s) where useful.
- Conversation history for AI: temporary in-memory storage for MVP.
- Structured output schema: defined during backend implementation (not pre-defined in planning phase).
- Testing defaults:
  - Frontend unit/integration: Vitest + Testing Library.
  - Frontend e2e: Playwright.
  - Backend unit/API: Pytest + FastAPI `TestClient`.

## Phase Workflow Rule

- Complete one part at a time.
- Run listed tests for that part.
- Confirm success criteria.
- Pause for user approval before starting the next part.

## Part 1 - Plan and Frontend Documentation

### Implementation checklist

- [ ] Expand this plan into detailed, testable phases (this document).
- [ ] Add `frontend/AGENTS.md` documenting the current frontend codebase and behavior.
- [ ] Ask for user review and approval before scaffolding work starts.

### Test gate

- [ ] Documentation review only (no runtime tests required).

### Success criteria

- [ ] `docs/PLAN.md` contains actionable checklists, tests, and success criteria for Parts 2-10.
- [ ] `frontend/AGENTS.md` accurately describes existing frontend implementation and tests.
- [ ] User approves the plan.

## Part 2 - Scaffolding (Docker + FastAPI skeleton + scripts)

### Implementation checklist

- [ ] Create backend project in `backend/` using FastAPI.
- [ ] Add Python dependency management via `uv` (inside Docker flow).
- [ ] Create Dockerfile for a single-container app.
- [ ] Add root-level run wiring so container serves:
  - [ ] static hello-world HTML at `/`
  - [ ] sample API route (for smoke verification), e.g. `/api/health` or `/api/hello`
- [ ] Add start/stop scripts in `scripts/` for macOS, Linux, Windows.
- [ ] Add concise root README usage section for local run.

### Test gate

- [ ] Build image successfully.
- [ ] Start container via script.
- [ ] Confirm browser request to `/` returns hello-world page.
- [ ] Confirm API request returns expected JSON and HTTP 200.
- [ ] Stop container via script cleanly.

### Success criteria

- [ ] One command path to start and stop container on each OS.
- [ ] Container runs backend and serves both HTML and API.
- [ ] No manual one-off setup steps beyond `.env` and Docker.

## Part 3 - Serve Existing Frontend from Backend

### Implementation checklist

- [ ] Configure frontend production build output for static serving.
- [ ] Update Docker build to produce frontend static artifacts.
- [ ] Serve built frontend from FastAPI at `/`.
- [ ] Keep API routes under `/api/*`.
- [ ] Ensure asset paths and client routing work in containerized environment.

### Test gate

- [ ] Frontend unit tests pass (`vitest`).
- [ ] Frontend e2e smoke test passes in containerized run.
- [ ] Manual check: Kanban board renders at `/` with existing demo behavior.
- [ ] API route(s) still reachable under `/api/*`.

### Success criteria

- [ ] App root displays current Kanban demo from built frontend assets.
- [ ] Backend remains entrypoint for both static site and API.
- [ ] No regressions in existing frontend tests.

## Part 4 - Fake Sign-in Experience

### Implementation checklist

- [ ] Add login page/flow gated by hardcoded credentials.
- [ ] Implement simple server-backed session cookie behavior.
- [ ] Block access to Kanban routes when not authenticated.
- [ ] Add logout action and session clear behavior.
- [ ] Keep UX minimal and clear (MVP only).

### Test gate

- [ ] Backend tests for login success/failure and session checks.
- [ ] Frontend tests for login form validation and redirect flow.
- [ ] E2E tests:
  - [ ] unauthenticated user is redirected to login
  - [ ] `user`/`password` logs in successfully
  - [ ] logout returns user to login

### Success criteria

- [ ] Kanban is not visible without login.
- [ ] Correct credentials grant access consistently.
- [ ] Logout invalidates session and re-gates Kanban.

## Part 5 - Database Modeling

### Implementation checklist

- [ ] Design normalized SQLite schema for:
  - [ ] users
  - [ ] board(s)
  - [ ] columns
  - [ ] cards
- [ ] Add JSON field(s) for flexible metadata/history where useful.
- [ ] Document schema and rationale in `docs/` with examples.
- [ ] Define migration/init strategy for creating DB if missing.
- [ ] Request user sign-off on schema document before coding API behavior.

### Test gate

- [ ] Schema documentation review.
- [ ] Migration/init dry run creates expected tables and constraints.

### Success criteria

- [ ] Schema is normalized and supports one-board-per-user MVP.
- [ ] JSON usage is intentional and documented (not replacing core normalized entities).
- [ ] User approves the documented DB model.

## Part 6 - Backend Kanban API

### Implementation checklist

- [ ] Implement DB init-on-start (create DB if missing).
- [ ] Seed default user/board data where needed for MVP.
- [ ] Add API endpoints to:
  - [ ] read board data for authenticated user
  - [ ] update board state (column names, card CRUD, movement/order)
- [ ] Add request/response validation models.
- [ ] Add robust error handling for invalid operations.

### Test gate

- [ ] Pytest unit tests for service/repository layer.
- [ ] API tests for success and failure paths.
- [ ] DB creation test when file is absent.
- [ ] Auth-gated API tests.

### Success criteria

- [ ] Authenticated user can fully read/update board through API.
- [ ] DB is auto-created without manual bootstrap.
- [ ] API contracts are deterministic and covered by tests.

## Part 7 - Frontend + Backend Integration

### Implementation checklist

- [ ] Replace frontend in-memory board state with backend API calls.
- [ ] Load board data after login.
- [ ] Persist rename/add/delete/move actions through backend.
- [ ] Add loading/error UI states appropriate for MVP.
- [ ] Keep interactions responsive and avoid visual regressions.

### Test gate

- [ ] Frontend unit/integration tests for API-driven state.
- [ ] E2E tests for full persistence loop:
  - [ ] modify board
  - [ ] refresh page
  - [ ] confirm state persists
- [ ] Backend API tests still green.

### Success criteria

- [ ] Kanban behavior is persistent across reloads and restarts (DB-backed).
- [ ] Existing user interactions still work in API-driven mode.
- [ ] No critical regressions in drag/drop and card operations.

## Part 8 - AI Connectivity (OpenRouter smoke)

### Implementation checklist

- [ ] Add backend AI client using OpenRouter and env-based API key.
- [ ] Configure model `openai/gpt-oss-120b`.
- [ ] Add protected test/debug route or internal service call for connectivity check.
- [ ] Implement minimal `2+2` smoke invocation path.

### Test gate

- [ ] Automated/integration test that verifies successful model call (with safe mocking where needed).
- [ ] Manual smoke run in local container with real key confirms expected response content.

### Success criteria

- [ ] Backend can successfully call OpenRouter model from local container.
- [ ] Failures are surfaced clearly when API key or network is invalid.

## Part 9 - AI Board-Aware Structured Output

### Implementation checklist

- [ ] Define structured output schema during implementation (backend-side).
- [ ] Build AI prompt pipeline with:
  - [ ] current board JSON
  - [ ] user question
  - [ ] temporary in-memory conversation history
- [ ] Parse and validate structured response:
  - [ ] assistant reply text
  - [ ] optional board mutation payload
- [ ] Apply valid board updates through existing backend data layer.
- [ ] Handle invalid/partial model outputs safely.

### Test gate

- [ ] Unit tests for schema validation and parser behavior.
- [ ] Service tests for mutation application rules.
- [ ] Integration tests for end-to-end AI request with mocked model responses.

### Success criteria

- [ ] AI responses always return a user-facing message.
- [ ] Optional board changes are validated before persistence.
- [ ] Conversation history works for the runtime process lifetime (MVP in-memory scope).

## Part 10 - Sidebar AI Chat UI

### Implementation checklist

- [ ] Build sidebar chat UI integrated into current Kanban layout.
- [ ] Add message history rendering and input interactions.
- [ ] Wire chat submit to backend AI endpoint.
- [ ] If AI returns board updates, refresh UI state automatically.
- [ ] Preserve visual consistency with project color scheme.

### Test gate

- [ ] Frontend tests for chat interactions and UI states.
- [ ] E2E tests covering:
  - [ ] sending a chat message
  - [ ] receiving assistant response
  - [ ] AI-triggered board update reflected in UI
- [ ] Regression tests for core Kanban interactions.

### Success criteria

- [ ] Sidebar chat is fully usable in MVP flow.
- [ ] AI can update board through structured backend response path.
- [ ] UI remains stable and responsive after AI-driven updates.

## Definition of Done (MVP)

- [ ] Single container starts app locally with scripts.
- [ ] Login gating works with dummy credentials.
- [ ] Kanban persists via backend + SQLite.
- [ ] AI chat is connected through OpenRouter and can optionally mutate board.
- [ ] All phase test gates pass.