from pathlib import Path
from secrets import token_urlsafe

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from app import ai, ai_chat, db

app = FastAPI(title="PM MVP Backend")

STATIC_DIR = Path(__file__).resolve().parent / "static"
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "pm.db"
SESSION_COOKIE_NAME = "pm_session"
MVP_USERNAME = "user"
MVP_PASSWORD = "password"
ACTIVE_SESSIONS: dict[str, str] = {}
CONVERSATION_HISTORY: dict[int, list[dict[str, str]]] = {}

LOGIN_PAGE_HTML = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Sign in - PM MVP</title>
    <style>
      :root {
        --accent-yellow: #ecad0a;
        --primary-blue: #209dd7;
        --secondary-purple: #753991;
        --navy-dark: #032147;
        --gray-text: #888888;
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        min-height: 100vh;
        display: grid;
        place-items: center;
        background: #f7f8fb;
        color: var(--navy-dark);
        font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
      }
      .card {
        width: min(420px, calc(100vw - 32px));
        border: 1px solid rgba(3, 33, 71, 0.12);
        border-radius: 20px;
        background: #fff;
        padding: 24px;
        box-shadow: 0 12px 32px rgba(3, 33, 71, 0.12);
      }
      h1 {
        margin: 0 0 8px;
        font-size: 1.6rem;
      }
      p {
        margin: 0 0 20px;
        color: var(--gray-text);
      }
      label {
        display: block;
        font-size: 0.85rem;
        font-weight: 600;
        margin-bottom: 6px;
      }
      input {
        width: 100%;
        border: 1px solid rgba(3, 33, 71, 0.18);
        border-radius: 12px;
        padding: 10px 12px;
        margin-bottom: 14px;
      }
      button {
        width: 100%;
        border: none;
        border-radius: 999px;
        padding: 11px 14px;
        background: var(--secondary-purple);
        color: #fff;
        font-weight: 700;
        cursor: pointer;
      }
      .hint {
        margin-top: 12px;
        font-size: 0.8rem;
      }
      .error {
        margin-top: 10px;
        min-height: 1.1rem;
        font-size: 0.9rem;
        color: #b00020;
      }
    </style>
  </head>
  <body>
    <main class="card">
      <h1>Sign in</h1>
      <p>Use the MVP credentials to access the Kanban board.</p>
      <form id="login-form">
        <label for="username">Username</label>
        <input id="username" name="username" type="text" autocomplete="username" required />
        <label for="password">Password</label>
        <input id="password" name="password" type="password" autocomplete="current-password" required />
        <button type="submit">Sign in</button>
        <div class="error" id="error"></div>
      </form>
      <div class="hint">MVP credentials: <strong>user</strong> / <strong>password</strong></div>
    </main>
    <script>
      const form = document.getElementById("login-form");
      const errorEl = document.getElementById("error");
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        errorEl.textContent = "";
        const formData = new FormData(form);
        const username = String(formData.get("username") || "");
        const password = String(formData.get("password") || "");
        try {
          const response = await fetch("/api/auth/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password })
          });
          if (!response.ok) {
            errorEl.textContent = "Invalid username or password.";
            return;
          }
          window.location.href = "/";
        } catch (error) {
          errorEl.textContent = "Unable to sign in. Try again.";
        }
      });
    </script>
  </body>
</html>
"""


class LoginPayload(BaseModel):
    username: str
    password: str


class RenameColumnPayload(BaseModel):
    title: str = Field(min_length=1, max_length=120)


class CreateCardPayload(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    details: str = Field(default="", max_length=5000)


class UpdateCardPayload(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    details: str = Field(default="", max_length=5000)


class MoveCardPayload(BaseModel):
    target_column_id: int
    target_position: int | None = Field(default=None, ge=0)


class AIChatPayload(BaseModel):
    message: str = Field(min_length=1, max_length=6000)


def is_authenticated(request: Request) -> bool:
    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    return bool(session_token and session_token in ACTIVE_SESSIONS)


def get_authenticated_user_id(request: Request) -> int:
    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    username = ACTIVE_SESSIONS.get(session_token or "")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    user = db.get_user_by_username(DB_PATH, username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return int(user["id"])


def clear_session(request: Request, response: Response) -> None:
    ACTIVE_SESSIONS.pop(request.cookies.get(SESSION_COOKIE_NAME, ""), None)
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")


def static_path_for(full_path: str) -> Path:
    if not full_path or full_path == "/":
        return STATIC_DIR / "index.html"
    clean_path = full_path.lstrip("/")
    target_path = (STATIC_DIR / clean_path).resolve()
    static_root = STATIC_DIR.resolve()
    if static_root not in target_path.parents and target_path != static_root:
        return STATIC_DIR / "index.html"
    if target_path.is_dir():
        return target_path / "index.html"
    return target_path


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/hello")
def hello() -> dict[str, str]:
    return {"message": "hello world"}


@app.on_event("startup")
def startup() -> None:
    ACTIVE_SESSIONS.clear()
    CONVERSATION_HISTORY.clear()
    db.init_database(DB_PATH, MVP_USERNAME, MVP_PASSWORD)


@app.post("/api/auth/login")
async def login(payload: LoginPayload) -> Response:
    user = db.get_user_by_username(DB_PATH, payload.username)
    is_valid = user is not None and (
        user["password_hash"] == db.hash_password(payload.password)
    )
    if not is_valid:
        return JSONResponse(
            {"ok": False, "error": "Invalid credentials"}, status_code=401
        )
    session_token = token_urlsafe(32)
    ACTIVE_SESSIONS[session_token] = payload.username
    response = JSONResponse({"ok": True})
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_token,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )
    return response


@app.post("/api/auth/logout")
def logout(request: Request) -> Response:
    response = JSONResponse({"ok": True})
    clear_session(request, response)
    return response


@app.get("/logout")
def logout_and_redirect(request: Request) -> Response:
    response = RedirectResponse("/", status_code=303)
    clear_session(request, response)
    return response


@app.get("/api/auth/session")
def session(request: Request) -> dict[str, bool]:
    return {"authenticated": is_authenticated(request)}


@app.get("/api/board")
def get_board(request: Request) -> dict:
    user_id = get_authenticated_user_id(request)
    return db.get_board_payload(DB_PATH, user_id)


@app.patch("/api/columns/{column_id}")
def rename_column(column_id: int, payload: RenameColumnPayload, request: Request) -> dict:
    user_id = get_authenticated_user_id(request)
    ok = db.rename_column(DB_PATH, user_id, column_id, payload.title.strip())
    if not ok:
        raise HTTPException(status_code=404, detail="Column not found")
    return {"ok": True}


@app.post("/api/columns/{column_id}/cards")
def add_card(column_id: int, payload: CreateCardPayload, request: Request) -> dict:
    user_id = get_authenticated_user_id(request)
    card = db.create_card(
        DB_PATH,
        user_id,
        column_id,
        payload.title.strip(),
        payload.details.strip(),
    )
    if card is None:
        raise HTTPException(status_code=404, detail="Column not found")
    return {"ok": True, "card": card}


@app.patch("/api/cards/{card_id}")
def edit_card(card_id: int, payload: UpdateCardPayload, request: Request) -> dict:
    user_id = get_authenticated_user_id(request)
    card = db.update_card(
        DB_PATH,
        user_id,
        card_id,
        payload.title.strip(),
        payload.details.strip(),
    )
    if card is None:
        raise HTTPException(status_code=404, detail="Card not found")
    return {"ok": True, "card": card}


@app.post("/api/cards/{card_id}/move")
def move_card(card_id: int, payload: MoveCardPayload, request: Request) -> dict:
    user_id = get_authenticated_user_id(request)
    ok = db.move_card(
        DB_PATH,
        user_id,
        card_id,
        payload.target_column_id,
        payload.target_position,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Card or column not found")
    return {"ok": True}


@app.delete("/api/cards/{card_id}")
def remove_card(card_id: int, request: Request) -> dict:
    user_id = get_authenticated_user_id(request)
    ok = db.delete_card(DB_PATH, user_id, card_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Card not found")
    return {"ok": True}


@app.post("/api/ai/smoke")
def ai_smoke_test(request: Request) -> dict:
    _ = get_authenticated_user_id(request)
    try:
        answer = ai.run_smoke_test()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="OpenRouter request failed") from exc
    return {"ok": True, "model": ai.OPENROUTER_MODEL, "response": answer}


@app.post("/api/ai/chat")
def ai_chat_route(payload: AIChatPayload, request: Request) -> dict:
    user_id = get_authenticated_user_id(request)
    board_payload = db.get_board_payload(DB_PATH, user_id)
    history = CONVERSATION_HISTORY.get(user_id, [])
    messages = ai_chat.build_ai_messages(board_payload, payload.message, history)

    try:
        raw_output = ai.send_chat_messages_with_env(messages)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="OpenRouter request failed") from exc

    parse_error = False
    applied_operations: list[str] = []
    updated_board = board_payload

    try:
        structured = ai_chat.parse_structured_response(raw_output)
        assistant_response = structured.assistant_response
    except ValueError:
        parse_error = True
        assistant_response = (
            "I could not format a valid structured response. "
            "No board changes were applied."
        )
        structured = ai_chat.StructuredAssistantResponse(
            assistant_response=assistant_response,
            board_update=None,
        )

    board_update = structured.board_update
    if not parse_error and board_update is not None:
        for action in board_update.rename_columns:
            if db.rename_column(DB_PATH, user_id, action.column_id, action.title.strip()):
                applied_operations.append(f"renamed column {action.column_id}")
        for action in board_update.create_cards:
            created = db.create_card(
                DB_PATH,
                user_id,
                action.column_id,
                action.title.strip(),
                action.details.strip(),
            )
            if created is not None:
                applied_operations.append(f"created card {created['id']}")
        for action in board_update.update_cards:
            updated = db.update_card(
                DB_PATH,
                user_id,
                action.card_id,
                action.title.strip(),
                action.details.strip(),
            )
            if updated is not None:
                applied_operations.append(f"updated card {action.card_id}")
        for action in board_update.move_cards:
            moved = db.move_card(
                DB_PATH,
                user_id,
                action.card_id,
                action.target_column_id,
                action.target_position,
            )
            if moved:
                applied_operations.append(f"moved card {action.card_id}")
        for card_id in board_update.delete_cards:
            deleted = db.delete_card(DB_PATH, user_id, card_id)
            if deleted:
                applied_operations.append(f"deleted card {card_id}")

        updated_board = db.get_board_payload(DB_PATH, user_id)

    history.append({"role": "user", "content": payload.message})
    history.append({"role": "assistant", "content": assistant_response})
    CONVERSATION_HISTORY[user_id] = history[-20:]

    return {
        "ok": True,
        "model": ai.OPENROUTER_MODEL,
        "response": assistant_response,
        "parse_error": parse_error,
        "applied_operations": applied_operations,
        "board": updated_board,
    }


@app.get("/{full_path:path}", response_class=HTMLResponse, response_model=None)
def app_routes(full_path: str, request: Request) -> Response:
    if not is_authenticated(request):
        return HTMLResponse(LOGIN_PAGE_HTML)

    target_path = static_path_for(full_path)
    if target_path.exists():
        return FileResponse(target_path)
    return HTMLResponse(
        "<h1>Frontend static build is not available yet.</h1>", status_code=503
    )
