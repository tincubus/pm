import hashlib
import sqlite3
from pathlib import Path

DEFAULT_COLUMNS: list[tuple[str, str]] = [
    ("col-backlog", "Backlog"),
    ("col-discovery", "Discovery"),
    ("col-progress", "In Progress"),
    ("col-review", "Review"),
    ("col-done", "Done"),
]

DEFAULT_CARDS: list[tuple[str, str, str]] = [
    (
        "col-backlog",
        "Align roadmap themes",
        "Draft quarterly themes with impact statements and metrics.",
    ),
    (
        "col-backlog",
        "Gather customer signals",
        "Review support tags, sales notes, and churn feedback.",
    ),
    (
        "col-discovery",
        "Prototype analytics view",
        "Sketch initial dashboard layout and key drill-downs.",
    ),
    (
        "col-progress",
        "Refine status language",
        "Standardize column labels and tone across the board.",
    ),
    (
        "col-progress",
        "Design card layout",
        "Add hierarchy and spacing for scanning dense lists.",
    ),
    (
        "col-review",
        "QA micro-interactions",
        "Verify hover, focus, and loading states.",
    ),
    (
        "col-done",
        "Ship marketing page",
        "Final copy approved and asset pack delivered.",
    ),
    (
        "col-done",
        "Close onboarding sprint",
        "Document release notes and share internally.",
    ),
]


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def get_connection(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_database(db_path: Path, mvp_username: str, mvp_password: str) -> None:
    with get_connection(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
              id INTEGER PRIMARY KEY,
              username TEXT NOT NULL UNIQUE,
              password_hash TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

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
            """
        )

        user = conn.execute(
            "SELECT id FROM users WHERE username = ?",
            (mvp_username,),
        ).fetchone()
        if user is None:
            conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (mvp_username, hash_password(mvp_password)),
            )
            user = conn.execute(
                "SELECT id FROM users WHERE username = ?",
                (mvp_username,),
            ).fetchone()
        user_id = int(user["id"])

        board = conn.execute(
            "SELECT id FROM boards WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if board is None:
            conn.execute(
                "INSERT INTO boards (user_id, name, settings_json) VALUES (?, ?, '{}')",
                (user_id, "My Project Board"),
            )
            board = conn.execute(
                "SELECT id FROM boards WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        board_id = int(board["id"])

        existing_columns = conn.execute(
            "SELECT COUNT(*) AS count FROM columns WHERE board_id = ?",
            (board_id,),
        ).fetchone()
        if int(existing_columns["count"]) == 0:
            for idx, (column_key, title) in enumerate(DEFAULT_COLUMNS):
                conn.execute(
                    """
                    INSERT INTO columns (board_id, key, title, position, meta_json)
                    VALUES (?, ?, ?, ?, '{}')
                    """,
                    (board_id, column_key, title, idx),
                )

        existing_cards = conn.execute(
            "SELECT COUNT(*) AS count FROM cards WHERE board_id = ?",
            (board_id,),
        ).fetchone()
        if int(existing_cards["count"]) == 0:
            column_rows = conn.execute(
                "SELECT id, key FROM columns WHERE board_id = ?",
                (board_id,),
            ).fetchall()
            column_id_by_key = {row["key"]: int(row["id"]) for row in column_rows}
            card_position_by_column: dict[int, int] = {}
            for column_key, title, details in DEFAULT_CARDS:
                column_id = column_id_by_key[column_key]
                position = card_position_by_column.get(column_id, 0)
                card_position_by_column[column_id] = position + 1
                conn.execute(
                    """
                    INSERT INTO cards (board_id, column_id, title, details, position, meta_json)
                    VALUES (?, ?, ?, ?, ?, '{}')
                    """,
                    (board_id, column_id, title, details, position),
                )


def get_user_by_username(db_path: Path, username: str) -> sqlite3.Row | None:
    with get_connection(db_path) as conn:
        return conn.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()


def get_board_for_user(db_path: Path, user_id: int) -> sqlite3.Row | None:
    with get_connection(db_path) as conn:
        return conn.execute(
            "SELECT id, name FROM boards WHERE user_id = ?",
            (user_id,),
        ).fetchone()


def get_board_payload(db_path: Path, user_id: int) -> dict:
    with get_connection(db_path) as conn:
        board = conn.execute(
            "SELECT id, name FROM boards WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if board is None:
            raise ValueError("Board not found for user")
        board_id = int(board["id"])

        column_rows = conn.execute(
            """
            SELECT id, key, title, position
            FROM columns
            WHERE board_id = ?
            ORDER BY position ASC, id ASC
            """,
            (board_id,),
        ).fetchall()
        card_rows = conn.execute(
            """
            SELECT id, column_id, title, details, position
            FROM cards
            WHERE board_id = ?
            ORDER BY position ASC, id ASC
            """,
            (board_id,),
        ).fetchall()

        cards: dict[str, dict] = {}
        card_ids_by_column: dict[int, list[int]] = {}
        for row in card_rows:
            card_id = int(row["id"])
            column_id = int(row["column_id"])
            cards[str(card_id)] = {
                "id": card_id,
                "title": row["title"],
                "details": row["details"],
                "columnId": column_id,
                "position": int(row["position"]),
            }
            card_ids_by_column.setdefault(column_id, []).append(card_id)

        columns: list[dict] = []
        for row in column_rows:
            column_id = int(row["id"])
            columns.append(
                {
                    "id": column_id,
                    "key": row["key"],
                    "title": row["title"],
                    "position": int(row["position"]),
                    "cardIds": card_ids_by_column.get(column_id, []),
                }
            )

        return {
            "id": board_id,
            "name": board["name"],
            "columns": columns,
            "cards": cards,
        }


def rename_column(
    db_path: Path,
    user_id: int,
    column_id: int,
    title: str,
) -> bool:
    with get_connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT c.id
            FROM columns c
            JOIN boards b ON b.id = c.board_id
            WHERE c.id = ? AND b.user_id = ?
            """,
            (column_id, user_id),
        ).fetchone()
        if row is None:
            return False
        conn.execute(
            "UPDATE columns SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (title, column_id),
        )
        return True


def create_card(
    db_path: Path,
    user_id: int,
    column_id: int,
    title: str,
    details: str,
) -> dict | None:
    with get_connection(db_path) as conn:
        target = conn.execute(
            """
            SELECT c.id, c.board_id
            FROM columns c
            JOIN boards b ON b.id = c.board_id
            WHERE c.id = ? AND b.user_id = ?
            """,
            (column_id, user_id),
        ).fetchone()
        if target is None:
            return None
        board_id = int(target["board_id"])
        last_position = conn.execute(
            "SELECT COALESCE(MAX(position), -1) AS max_position FROM cards WHERE column_id = ?",
            (column_id,),
        ).fetchone()
        next_position = int(last_position["max_position"]) + 1
        cursor = conn.execute(
            """
            INSERT INTO cards (board_id, column_id, title, details, position, meta_json)
            VALUES (?, ?, ?, ?, ?, '{}')
            """,
            (board_id, column_id, title, details, next_position),
        )
        card_id = int(cursor.lastrowid)
        return {
            "id": card_id,
            "title": title,
            "details": details,
            "columnId": column_id,
            "position": next_position,
        }


def delete_card(db_path: Path, user_id: int, card_id: int) -> bool:
    with get_connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT c.id, c.column_id, c.position
            FROM cards c
            JOIN boards b ON b.id = c.board_id
            WHERE c.id = ? AND b.user_id = ?
            """,
            (card_id, user_id),
        ).fetchone()
        if row is None:
            return False

        conn.execute("DELETE FROM cards WHERE id = ?", (card_id,))
        conn.execute(
            "UPDATE cards SET position = position - 1 WHERE column_id = ? AND position > ?",
            (int(row["column_id"]), int(row["position"])),
        )
        return True


def update_card(
    db_path: Path,
    user_id: int,
    card_id: int,
    title: str,
    details: str,
) -> dict | None:
    with get_connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT c.id, c.column_id, c.position
            FROM cards c
            JOIN boards b ON b.id = c.board_id
            WHERE c.id = ? AND b.user_id = ?
            """,
            (card_id, user_id),
        ).fetchone()
        if row is None:
            return None
        conn.execute(
            """
            UPDATE cards
            SET title = ?, details = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (title, details, card_id),
        )
        return {
            "id": card_id,
            "title": title,
            "details": details,
            "columnId": int(row["column_id"]),
            "position": int(row["position"]),
        }


def move_card(
    db_path: Path,
    user_id: int,
    card_id: int,
    target_column_id: int,
    target_position: int | None,
) -> bool:
    with get_connection(db_path) as conn:
        card = conn.execute(
            """
            SELECT c.id, c.board_id, c.column_id
            FROM cards c
            JOIN boards b ON b.id = c.board_id
            WHERE c.id = ? AND b.user_id = ?
            """,
            (card_id, user_id),
        ).fetchone()
        if card is None:
            return False
        board_id = int(card["board_id"])
        source_column_id = int(card["column_id"])

        target = conn.execute(
            """
            SELECT c.id
            FROM columns c
            WHERE c.id = ? AND c.board_id = ?
            """,
            (target_column_id, board_id),
        ).fetchone()
        if target is None:
            return False

        source_ids = [
            int(row["id"])
            for row in conn.execute(
                "SELECT id FROM cards WHERE column_id = ? ORDER BY position ASC, id ASC",
                (source_column_id,),
            ).fetchall()
        ]
        target_ids = source_ids if source_column_id == target_column_id else [
            int(row["id"])
            for row in conn.execute(
                "SELECT id FROM cards WHERE column_id = ? ORDER BY position ASC, id ASC",
                (target_column_id,),
            ).fetchall()
        ]

        if card_id not in source_ids:
            return False

        source_ids.remove(card_id)
        if source_column_id == target_column_id:
            target_ids = source_ids

        if target_position is None:
            insert_at = len(target_ids)
        else:
            insert_at = max(0, min(target_position, len(target_ids)))
        target_ids.insert(insert_at, card_id)

        # Move affected rows to temporary positions first to avoid
        # UNIQUE(column_id, position) collisions during reordering.
        if source_column_id == target_column_id:
            conn.execute(
                "UPDATE cards SET position = position + 1000 WHERE column_id = ?",
                (source_column_id,),
            )
        else:
            conn.execute(
                """
                UPDATE cards
                SET column_id = ?, position = -1, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (target_column_id, card_id),
            )
            conn.execute(
                "UPDATE cards SET position = position + 1000 WHERE column_id IN (?, ?)",
                (source_column_id, target_column_id),
            )

        for position, id_value in enumerate(source_ids):
            conn.execute(
                "UPDATE cards SET position = ? WHERE id = ?",
                (position, id_value),
            )
        for position, id_value in enumerate(target_ids):
            conn.execute(
                "UPDATE cards SET position = ? WHERE id = ?",
                (position, id_value),
            )
        return True
