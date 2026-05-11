# Database Schema

This document describes the MVP SQLite data model for the Kanban app. It is kept in sync with the live schema in [backend/app/db.py](../backend/app/db.py).

## Goals

- Keep core Kanban entities normalized (`users`, `boards`, `columns`, `cards`).
- Support one board per user for MVP, while preserving future multi-user expansion.
- Use JSON only for flexible metadata fields, not for core relational structure.
- Keep initialization simple and deterministic with idempotent table creation and seeding.

## Entity Model

### `users`

- One row per user. Login is by email; `username` is retained for legacy compatibility with the seeded user and is set equal to the email for newly-registered users.
- MVP seeds one user (`username = "user"`, `email = "user@local.pm"`).

Columns:

- `id` INTEGER PRIMARY KEY
- `username` TEXT NOT NULL UNIQUE
- `email` TEXT (backfilled from `username || '@local.pm'` on first migration; unique index added separately)
- `password_hash` TEXT NOT NULL — scrypt format `scrypt$N$r$p$salt_hex$key_hex`
- `created_at` TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
- `updated_at` TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP

Indexes:

- `idx_users_email` UNIQUE on `(email)` — created as a separate `CREATE UNIQUE INDEX IF NOT EXISTS` so the column can be added by `ALTER TABLE` on existing DBs.

Notes:

- Passwords are hashed with `scrypt` (N=2^14, r=8, p=1) and a per-user 16-byte salt. Verification is constant-time.

### `boards`

- One board per user in MVP.
- Future-ready for additional board features and settings.

Columns:

- `id` INTEGER PRIMARY KEY
- `user_id` INTEGER NOT NULL
- `name` TEXT NOT NULL
- `settings_json` TEXT NOT NULL DEFAULT '{}'
- `created_at` TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
- `updated_at` TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP

Constraints:

- `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE`
- `UNIQUE(user_id)` for MVP one-board-per-user enforcement

JSON usage:

- `settings_json` stores optional board-level settings (for example theme/display flags in future).

### `columns`

- Board columns with deterministic ordering.

Columns:

- `id` INTEGER PRIMARY KEY
- `board_id` INTEGER NOT NULL
- `key` TEXT NOT NULL
- `title` TEXT NOT NULL
- `position` INTEGER NOT NULL
- `meta_json` TEXT NOT NULL DEFAULT '{}'
- `created_at` TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
- `updated_at` TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP

Constraints:

- `FOREIGN KEY (board_id) REFERENCES boards(id) ON DELETE CASCADE`
- `UNIQUE(board_id, key)` (stable identifier per board)
- `UNIQUE(board_id, position)` (single column per position)

JSON usage:

- `meta_json` reserved for optional UI metadata (future badges, color overrides, etc.).

### `cards`

- Card content and order within each column.

Columns:

- `id` INTEGER PRIMARY KEY
- `board_id` INTEGER NOT NULL
- `column_id` INTEGER NOT NULL
- `title` TEXT NOT NULL
- `details` TEXT NOT NULL
- `position` INTEGER NOT NULL
- `meta_json` TEXT NOT NULL DEFAULT '{}'
- `created_at` TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
- `updated_at` TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP

Constraints:

- `FOREIGN KEY (board_id) REFERENCES boards(id) ON DELETE CASCADE`
- `FOREIGN KEY (column_id) REFERENCES columns(id) ON DELETE CASCADE`
- `UNIQUE(column_id, position)` (ordering inside a column)

JSON usage:

- `meta_json` stores optional card metadata (future labels, due dates, AI annotations, etc.).

### `sessions`

- One row per active login. Session cookie value is a 32-byte URL-safe token; only its SHA-256 hash is stored.
- Cleaned up on startup and on each successful login/register.

Columns:

- `id` INTEGER PRIMARY KEY
- `user_id` INTEGER NOT NULL
- `token_hash` TEXT NOT NULL UNIQUE — hex SHA-256 of the cookie value
- `expires_at` INTEGER NOT NULL — Unix timestamp; sliding TTL of 7 days, refreshed on every authenticated request
- `created_at` TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
- `updated_at` TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP

Constraints:

- `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE`

Indexes:

- `idx_sessions_user_id` on `(user_id)`
- `idx_sessions_expires_at` on `(expires_at)`

## DDL (Reference)

```sql
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY,
  username TEXT NOT NULL UNIQUE,
  email TEXT,
  password_hash TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email);

CREATE TABLE IF NOT EXISTS boards (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL,
  name TEXT NOT NULL,
  settings_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  UNIQUE(user_id)
);

CREATE TABLE IF NOT EXISTS columns (
  id INTEGER PRIMARY KEY,
  board_id INTEGER NOT NULL,
  key TEXT NOT NULL,
  title TEXT NOT NULL,
  position INTEGER NOT NULL,
  meta_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (board_id) REFERENCES boards(id) ON DELETE CASCADE,
  UNIQUE(board_id, key),
  UNIQUE(board_id, position)
);

CREATE TABLE IF NOT EXISTS cards (
  id INTEGER PRIMARY KEY,
  board_id INTEGER NOT NULL,
  column_id INTEGER NOT NULL,
  title TEXT NOT NULL,
  details TEXT NOT NULL,
  position INTEGER NOT NULL,
  meta_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (board_id) REFERENCES boards(id) ON DELETE CASCADE,
  FOREIGN KEY (column_id) REFERENCES columns(id) ON DELETE CASCADE,
  UNIQUE(column_id, position)
);

CREATE INDEX IF NOT EXISTS idx_boards_user_id ON boards(user_id);
CREATE INDEX IF NOT EXISTS idx_columns_board_id ON columns(board_id);
CREATE INDEX IF NOT EXISTS idx_cards_board_id ON cards(board_id);
CREATE INDEX IF NOT EXISTS idx_cards_column_id ON cards(column_id);

CREATE TABLE IF NOT EXISTS sessions (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL,
  token_hash TEXT NOT NULL UNIQUE,
  expires_at INTEGER NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at);
```

## Seed Data Strategy

On first run (when DB is empty):

1. Insert MVP user `user` with hashed `password`.
2. Insert one board for that user (for example `My Project Board`).
3. Insert default five columns:
   - Backlog
   - Discovery
   - In Progress
   - Review
   - Done
4. Insert starter cards matching current frontend demo.

Seeding must be idempotent:

- Use existence checks (by username, board unique key, etc.).
- Run in a single transaction.

## Initialization / Migration Approach

For MVP, keep migration approach simple:

- On backend startup:
  - Ensure DB directory exists (for example `backend/data/`).
  - Open SQLite file (`pm.db`) and enable foreign keys.
  - Execute `CREATE TABLE IF NOT EXISTS` DDL and required indexes.
  - Run idempotent seed routine.

This gives a predictable "create DB if missing" flow without adding external migration tooling yet.

## Why This Fits MVP Constraints

- One board per user is enforced in DB (`UNIQUE(user_id)` on `boards`).
- Core board/column/card structure is relational and queryable.
- JSON fields are limited to optional metadata and do not replace normalized entities.
- Easy to evolve in Part 6 and Part 7 when APIs and persistence wiring are added.

## Out of Scope for Part 5

- No API implementation changes yet.
- No conversation-history persistence (kept in-memory for MVP per agreed decision).
- No AI-specific schema yet (handled in later parts if needed).
