# Code Review

Comprehensive review of the PM MVP repo. Findings are categorized by severity. Each finding has a location, description, and recommended action.

Scope reviewed: backend (`backend/`), frontend (`frontend/`), Docker + scripts, docs, tests. ~3.2k LOC total.

## Executive summary

The MVP is functionally complete and well-scoped, with parameterized SQL, scrypt password hashing, hashed session tokens, and httponly+SameSite cookies. Tests cover the critical paths.

The blocking issues are tooling: `npm run lint` fails (2 errors), `tsc --noEmit` fails project-wide (test globals not typed), and `npm audit` reports 9 vulnerabilities (6 high) including Next.js CVEs. Several docs are stale relative to the schema and feature state.

The most impactful runtime concern is column rename firing a backend write on every keystroke with no debounce, followed by a full board refetch. The AI chat path applies board mutations across separate transactions without rollback on partial failure.

## Findings

### Critical

#### C1. `npm run lint` is failing
**Location:** [frontend/src/components/KanbanBoard.tsx:477](frontend/src/components/KanbanBoard.tsx:477)
**Issue:** Two `react/no-unescaped-entities` errors on the placeholder string `Try: "Add a card to Backlog for API docs."`. ESLint blocks on bare `"` inside JSX text.
**Action:** Replace with `&quot;` or single quotes / template literal — e.g. `Try: &quot;Add a card to Backlog for API docs.&quot;`. Run `npm run lint` until clean.

#### C2. `tsc --noEmit` fails across all test files
**Location:** [frontend/src/components/KanbanBoard.test.tsx:1](frontend/src/components/KanbanBoard.test.tsx:1), [frontend/src/lib/kanban.test.ts:1](frontend/src/lib/kanban.test.ts:1)
**Issue:** `describe`, `it`, `expect`, `afterEach` are not in scope for the TypeScript compiler. `vitest.config.ts` enables `globals: true` (runtime injection works), but no triple-slash reference or `tsconfig.json` `types` entry makes them visible to `tsc`. The existing [frontend/src/test/vitest.d.ts](frontend/src/test/vitest.d.ts) references `vitest` and `@testing-library/jest-dom` but doesn't pull in `vitest/globals`.
**Action:** Either (a) add `"types": ["vitest/globals", "@testing-library/jest-dom"]` to `tsconfig.json`, or (b) change `frontend/src/test/vitest.d.ts` to `/// <reference types="vitest/globals" />`. Option (b) is least invasive. Verify with `npx tsc --noEmit`.

#### C3. 9 npm vulnerabilities (6 high) including Next.js
**Location:** [frontend/package-lock.json](frontend/package-lock.json)
**Issue:** `npm audit` reports high-severity advisories in `next` (HTTP request smuggling, CSRF bypasses, DoS), `vite`, `rollup`, `picomatch`, `minimatch`, `flatted`, and moderate in `ajv`, `brace-expansion`, `postcss`. Several are direct dependencies.
**Action:** Run `npm audit fix` first. For any remaining, evaluate `npm audit fix --force` per package and re-run unit + e2e tests. The Next.js CVE list specifically includes "null origin can bypass Server Actions CSRF checks" — relevant given this app uses POST/PATCH/DELETE for board mutations.

#### C4. Docs drifted from schema and feature state
**Location:** [docs/DB_SCHEMA.md](docs/DB_SCHEMA.md), [backend/AGENTS.md](backend/AGENTS.md)
**Issue:**
- [docs/DB_SCHEMA.md](docs/DB_SCHEMA.md) describes `users` with columns `id, username, password_hash, created_at, updated_at` — but the live schema in [backend/app/db.py:194](backend/app/db.py:194) also includes `email` (with a `UNIQUE` index added separately) and a whole `sessions` table that isn't documented at all.
- [backend/AGENTS.md](backend/AGENTS.md) says scope "does not yet include: full frontend sidebar AI chat integration" — but it IS integrated ([frontend/src/components/KanbanBoard.tsx:461](frontend/src/components/KanbanBoard.tsx:461)) and exercised by tests.
**Action:** Update [docs/DB_SCHEMA.md](docs/DB_SCHEMA.md) to document the `email` column, the email unique index, and the `sessions` table (DDL is in [backend/app/db.py:248](backend/app/db.py:248)). Remove the stale scope-gap note from [backend/AGENTS.md](backend/AGENTS.md).

### High

#### H1. Column rename writes to backend on every keystroke
**Location:** [frontend/src/components/KanbanColumn.tsx:43](frontend/src/components/KanbanColumn.tsx:43) → [frontend/src/components/KanbanBoard.tsx:237](frontend/src/components/KanbanBoard.tsx:237)
**Issue:** `<input onChange={(event) => onRename(column.id, event.target.value)} />` fires `handleRenameColumn` on every character. Each call issues a `PATCH /api/columns/{id}` AND then `loadBoardFromBackend()` — a full board refetch. Typing "Roadmap themes" emits ~14 PATCHes and 14 GETs.
**Action:** Debounce (e.g. 400ms) or commit on blur/Enter. The latter is simpler and matches typical Kanban UX. Apply the same review to any other onChange-driven mutations.

#### H2. AI chat board mutations are not transactional
**Location:** [backend/app/main.py:479](backend/app/main.py:479)
**Issue:** Each operation in `board_update` (`rename_column`, `create_card`, `update_card`, `move_card`, `delete_card`) calls a separate `db.*` helper, each of which opens its own connection and commits independently. If the AI proposes 3 valid ops and a 4th invalid one, the first 3 are already persisted and there is no rollback. The response truthfully reports `applied_operations`, but the board can land in a state the user did not intend.
**Action:** Either (a) accept and document the "partial apply" semantics in the user-facing message, or (b) introduce a single transactional helper in [backend/app/db.py](backend/app/db.py) that takes the full mutation payload and applies it under one connection with `BEGIN ... COMMIT/ROLLBACK`. Option (b) is preferable.

#### H3. `move_card` reorder trick assumes <1000 cards per column
**Location:** [backend/app/db.py:664](backend/app/db.py:664)
**Issue:** To avoid violating `UNIQUE(column_id, position)` during reorder, the code shifts all affected rows by `+1000` then renumbers. With ≥1000 cards in a column the shifted positions collide with existing ones and the second `UPDATE` errors. The comment notes the technique but not the limit.
**Action:** Replace the shift trick with either: (a) drop `UNIQUE(column_id, position)` (the reorder code maintains uniqueness anyway), or (b) shift by `+1_000_000` (still finite but practically safe). Option (a) removes the brittleness entirely. If keeping the constraint, document the cap in a brief comment or assertion.

#### H4. Partial path-traversal defense in static handler
**Location:** [backend/app/main.py:267](backend/app/main.py:267)
**Issue:** The current check is `if static_root not in target_path.parents and target_path != static_root`. It correctly blocks `../../etc/passwd` because the resolved target leaves `STATIC_DIR`. But it returns `STATIC_DIR / "index.html"` (200 OK) instead of a 404 for the abusive request — a low-impact defense-in-depth gap, but it masks attempts that should be logged/blocked.
**Action:** Return a 404 (or redirect to `/`) for paths that escape `STATIC_DIR`. The current 200 + index masquerade conflates "missing path" and "traversal attempt".

### Medium

#### M1. Multiple DB connections per request
**Location:** [backend/app/db.py:123](backend/app/db.py:123) (`get_connection`), and every public helper below it
**Issue:** Every helper (`get_session_user_by_token`, `touch_session_expiry`, `create_session`, `rename_column`, …) opens its own `sqlite3.connect`. A single authenticated mutation request can open 3–5 connections. The `with` block commits but does not close — the connection is only closed at GC.
**Action:** For MVP scale this is fine functionally. Worth tracking as a follow-up. A minimal improvement: thread a connection through related calls (e.g. session check + touch in a single connection in `get_authenticated_user_id`). A proper fix is a FastAPI dependency-injected connection.

#### M2. Open registration with no rate limit, no email verification
**Location:** [backend/app/main.py:296](backend/app/main.py:296)
**Issue:** `/api/auth/register` accepts any payload, creates an account, and grants a session — no captcha, no rate limit, no email confirmation. For local MVP this is fine; for any networked deploy this is account-spam + DoS.
**Action:** Acceptable as-is for MVP. Before any deploy beyond localhost: add at minimum IP-based rate limiting and remove auto-login on register (require explicit login). Worth recording the decision in [AGENTS.md](AGENTS.md) "Limitations".

#### M3. User enumeration via register endpoint
**Location:** [backend/app/main.py:309](backend/app/main.py:309)
**Issue:** Returning `409 "Email is already registered"` lets an attacker probe which emails have accounts. Login already uses generic "Invalid credentials" — but register reveals existence.
**Action:** Either (a) accept this trade-off for MVP and document it, or (b) return a generic 200 "If your email is valid, check your inbox" and gate actual account creation on email verification. (a) is fine for now.

#### M4. Email format validation is `"@" in email`
**Location:** [backend/app/main.py:300](backend/app/main.py:300)
**Issue:** Accepts `a@`, `@`, `@@`, etc. The DB UNIQUE constraint catches duplicates but garbage emails get stored.
**Action:** Either add `email-validator` to deps and use Pydantic `EmailStr`, or apply a simple regex check (`^[^@\s]+@[^@\s]+\.[^@\s]+$`). Low cost, real DX win.

#### M5. `delete_expired_sessions` only runs on login/register
**Location:** [backend/app/main.py:240](backend/app/main.py:240)
**Issue:** Active sessions never trigger cleanup; an MVP that's never logged into anew accumulates expired rows.
**Action:** Call it from `startup()` too, or on a simple time-based throttle (e.g. once per hour gated by a module-level timestamp). Low priority.

#### M6. Deprecated `@app.on_event("startup")`
**Location:** [backend/app/main.py:290](backend/app/main.py:290)
**Issue:** FastAPI raises a DeprecationWarning during tests. Will be removed in a future version.
**Action:** Migrate to a `lifespan` async context manager. Five-line change.

#### M7. Frontend mutation pattern duplicated five times
**Location:** [frontend/src/components/KanbanBoard.tsx:213](frontend/src/components/KanbanBoard.tsx:213), [:243](frontend/src/components/KanbanBoard.tsx:243), [:269](frontend/src/components/KanbanBoard.tsx:269), [:302](frontend/src/components/KanbanBoard.tsx:302), and AI chat at [:350](frontend/src/components/KanbanBoard.tsx:350)
**Issue:** Each mutation does `fetch(...).then(response => response.ok ? loadBoardFromBackend() : noop)`. No error handling, no toasts, identical scaffolding repeated.
**Action:** Extract a `mutateBoard(method, url, body?)` helper that wraps fetch + error surfacing + refetch. Will also let you add optimistic UI later in one place.

#### M8. No optimistic UI
**Location:** [frontend/src/components/KanbanBoard.tsx](frontend/src/components/KanbanBoard.tsx) (all mutation handlers)
**Issue:** Every mutation waits for the network round-trip then full-board-refetches before the UI updates. Drag visibly snaps back if the network is slow.
**Action:** Apply changes locally first, send the request, revert on failure. For the MVP scope it's a nice-to-have, but it makes the app feel notably less laggy.

#### M9. Backend silently re-hashes legacy SHA-256 passwords
**Location:** [backend/app/db.py:117](backend/app/db.py:117), [backend/app/main.py:326](backend/app/main.py:326)
**Issue:** `verify_password` falls back to comparing against a legacy unsalted SHA-256 hash. The MVP has no shipped users with legacy hashes (the seed runs `hash_password` with scrypt), so this branch is dead code that adds complexity. If you do have legacy DBs in the wild, the silent rehash is correct.
**Action:** If no legacy DB exists, delete the legacy branch. If retaining for backward compatibility, add a comment naming when legacy hashes were emitted so it can be removed later.

### Low

#### L1. Dead code in `db.py` and `ai.py`
**Location:** [backend/app/db.py:297](backend/app/db.py:297) (`get_user_by_username`), [backend/app/db.py:406](backend/app/db.py:406) (`get_board_for_user`), [backend/app/ai.py:29](backend/app/ai.py:29) (`send_chat_prompt`)
**Issue:** Defined but never called from anywhere in the repo.
**Action:** Delete. Per AGENTS.md ("no extra features").

#### L2. Misleading `MVP_USERNAME` / `MVP_PASSWORD` constants
**Location:** [backend/app/main.py:17](backend/app/main.py:17)
**Issue:** Login is by email; these constants only drive seeding of the legacy `username="user"` row. The name implies they're used at runtime.
**Action:** Rename to `SEED_USERNAME` / `SEED_PASSWORD`, or pass them as parameters into `init_database` from a small `seed.py` module. Trivial cleanup.

#### L3. `username` column is redundant
**Location:** [backend/app/db.py:194](backend/app/db.py:194)
**Issue:** For users created via `/api/auth/register`, `username` equals `email`. Only the seeded user has `username="user"` separate from `email="user@local.pm"`.
**Action:** Decide on canonical login field (email) and either (a) drop `username` from the schema in a follow-up, or (b) document the divergence. Schema doc update tied to C4.

#### L4. Login HTML inlined as a 173-line string in `main.py`
**Location:** [backend/app/main.py:24-173](backend/app/main.py:24)
**Issue:** Mixing a long HTML/CSS/JS literal into the route file hurts readability.
**Action:** Move to `backend/app/templates/login.html` and serve via `FileResponse` or `HTMLResponse(open(...).read())`. Bonus: lets you test the HTML rendering independently.

#### L5. `KanbanBoard.tsx` is 526 lines
**Location:** [frontend/src/components/KanbanBoard.tsx](frontend/src/components/KanbanBoard.tsx)
**Issue:** Owns board state, dnd coordination, AI chat UI, network calls, and layout. Hard to test sections in isolation.
**Action:** Split the AI sidebar into `AISidebar.tsx` (takes `usesBackend`, `onBoardUpdate` callback). Possibly extract network helpers per M7.

#### L6. 503 for missing static paths is misleading
**Location:** [backend/app/main.py:542](backend/app/main.py:542)
**Issue:** Authenticated users hitting a path that doesn't exist see "Frontend static build is not available yet." with status 503. That's actually a build-broken message but it fires for any missing path.
**Action:** Return 404 with a generic message; reserve 503 for the genuine "static dir missing" case.

#### L7. Mac and Linux start scripts are byte-identical
**Location:** [scripts/start-mac.sh](scripts/start-mac.sh), [scripts/start-linux.sh](scripts/start-linux.sh)
**Issue:** Two copies of the same bash script.
**Action:** Symlink one to the other, or use a single `start.sh` and ship `start-mac.sh` as a thin wrapper. Same for `stop-*.sh`.

#### L8. Card edit UI not exposed in frontend
**Location:** [frontend/src/components/KanbanCard.tsx](frontend/src/components/KanbanCard.tsx) (no edit button), [backend/app/main.py:395](backend/app/main.py:395) (backend supports it)
**Issue:** The backend `PATCH /api/cards/{id}` endpoint and its tests exist, but the frontend Kanban card has only a Remove button. AGENTS.md feature ("cards can be moved and edited") is partially implemented in UI.
**Action:** Either build the edit affordance (inline title/details editor on card click), or remove the unused endpoint and tests. Per MVP requirements, build the affordance.

#### L9. No backend lint/format tooling
**Location:** [backend/pyproject.toml](backend/pyproject.toml)
**Issue:** No `ruff`, `black`, or `mypy` config. The Python is consistent by hand but there's nothing enforcing it.
**Action:** Add `ruff` to dev deps and a tiny `[tool.ruff]` config (line length, select rules). One-time setup; pays off as the codebase grows.

#### L10. Dockerfile runs as root
**Location:** [Dockerfile:11](Dockerfile:11)
**Issue:** No `USER` directive — container runs as root. Acceptable for local-only MVP, not for any shared host.
**Action:** Add a non-root user before `CMD`. Two-line change.

### Nits

- **N1.** [backend/app/main.py:209](backend/app/main.py:209) (`is_authenticated`) duplicates the session lookup in `get_authenticated_user_id`. The catch-all `/{full_path:path}` route uses the former and doesn't touch session expiry, so static-page visits don't extend the session. Mostly fine; just inconsistent.
- **N2.** [backend/app/main.py:534](backend/app/main.py:534): catch-all returns `HTMLResponse(LOGIN_PAGE_HTML)` with status 200 instead of 401 when unauthenticated. Conventional for browser UX (since you want the login form rendered) but means API clients can't distinguish "missing route" from "needs auth".
- **N3.** [frontend/src/components/KanbanBoard.tsx:208](frontend/src/components/KanbanBoard.tsx:208): same-column same-position drag still sends a move request. Add an early return when `sourceIndex === overIndex && sourceColumn.id === targetColumnUiId`.
- **N4.** [frontend/src/lib/kanban.ts:164](frontend/src/lib/kanban.ts:164): `createId` mixes `Math.random()` with `Date.now()` for fallback IDs. Fine for fallback mode. `crypto.randomUUID()` is more idiomatic.
- **N5.** [backend/app/db.py:269](backend/app/db.py:269): the migration `UPDATE users SET email = username || ?` is a one-time backfill that runs on every startup. Cheap, but does an unnecessary write each boot. Wrap in a check for any null/empty rows first.
- **N6.** `frontend/AGENTS.md` line 38 still lists "Card content is not editable after creation" as a known limit — consistent with reality (see L8), but if you fix L8 update the doc.

## Strengths

- **SQL**: every query is parameterized; no injection surface (full review of [backend/app/db.py](backend/app/db.py) confirms).
- **Password hashing**: scrypt with N=2^14, r=8, p=1; `hmac.compare_digest` for constant-time compare; per-user salt; auto-rehash path exists.
- **Session tokens**: 256-bit `secrets.token_urlsafe(32)`; stored as SHA-256 hash, never plaintext; httponly + SameSite=Lax + opt-in secure.
- **Path traversal**: defended in [backend/app/main.py:267](backend/app/main.py:267) using `Path.resolve()` + `parents` check (see H4 for a small refinement).
- **Schema**: clean normalization; JSON metadata fields used for genuine optional metadata only (per the documented intent).
- **Tests**: 15 backend + 7 frontend unit + 3 e2e all pass; auth, board CRUD, AI structured-output parsing, in-memory history, and DB auto-creation are all covered.
- **AI structured output**: `_extract_json_string` handles fenced code blocks and stray prose; Pydantic validation rejects malformed payloads; the error path returns a coherent fallback message.
- **Standards adherence**: no emojis anywhere in source (verified by Unicode scan); functions are short and focused; no obvious over-engineering.

## Prioritized action checklist

Tackle in this order. Each is small enough to be its own commit.

1. **Fix lint** — escape the quotes at [KanbanBoard.tsx:477](frontend/src/components/KanbanBoard.tsx:477). (C1)
2. **Fix tsc** — make Vitest globals visible to the compiler via [vitest.d.ts](frontend/src/test/vitest.d.ts) or `tsconfig.json` `types`. (C2)
3. **Update docs** — refresh [docs/DB_SCHEMA.md](docs/DB_SCHEMA.md) (email column, sessions table) and [backend/AGENTS.md](backend/AGENTS.md) (drop the stale AI scope note). (C4)
4. **Run `npm audit fix`** and re-run all three test suites. (C3)
5. **Debounce column rename** or switch to onBlur/Enter. (H1)
6. **Transactional AI mutations** — single `db.apply_ai_board_update(payload)` helper. (H2)
7. **Remove the 1000-row reorder cap** — drop `UNIQUE(column_id, position)` or shift by 1_000_000. (H3)
8. **Migrate `on_event` → `lifespan`**. (M6)
9. **Delete dead code** — `get_user_by_username`, `get_board_for_user`, `send_chat_prompt`. (L1)
10. **Rename misleading constants** (`MVP_*` → `SEED_*`). (L2)
11. **Optional**: extract login HTML to a template (L4), split AI sidebar component (L5), add ruff (L9), build card edit UI (L8).

## Out-of-scope items worth recording

If this app is ever exposed beyond localhost, the following move from "acceptable for MVP" to "blocker":
- Open registration without rate limit or email verification (M2).
- User enumeration via register 409 (M3).
- Dockerfile runs as root (L10).
- No CSP/HSTS/X-Frame-Options headers.
- `COOKIE_SECURE` defaults to false; must be flipped via env.

None of these are bugs in the current local-only scope.
