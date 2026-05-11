import os
import time
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
SESSION_TTL_SECONDS = 7 * 24 * 60 * 60
MIN_PASSWORD_LENGTH = 8
COOKIE_SECURE = os.getenv("PM_COOKIE_SECURE", "false").strip().lower() == "true"
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
      <p>Create an account or sign in to access your Kanban board.</p>
      <form id="login-form">
        <label for="email">Email</label>
        <input id="email" name="email" type="email" autocomplete="email" required />
        <label for="password">Password</label>
        <input id="password" name="password" type="password" autocomplete="current-password" required />
        <button type="submit">Sign in</button>
        <div class="error" id="error"></div>
      </form>
      <form id="signup-form" style="margin-top: 14px;">
        <label for="signup-email">New account email</label>
        <input id="signup-email" name="email" type="email" autocomplete="email" required />
        <label for="signup-password">New account password (min 8 chars)</label>
        <input id="signup-password" name="password" type="password" autocomplete="new-password" minlength="8" required />
        <button type="submit">Create account</button>
        <div class="error" id="signup-error"></div>
      </form>
      <div class="hint">Seeded test account: <strong>user@local.pm</strong> / <strong>password</strong></div>
    </main>
    <script>
      const form = document.getElementById("login-form");
      const errorEl = document.getElementById("error");
      const signupForm = document.getElementById("signup-form");
      const signupErrorEl = document.getElementById("signup-error");
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        errorEl.textContent = "";
        const formData = new FormData(form);
        const email = String(formData.get("email") || "");
        const password = String(formData.get("password") || "");
        try {
          const response = await fetch("/api/auth/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password })
          });
          if (!response.ok) {
            errorEl.textContent = "Invalid email or password.";
            return;
          }
          window.location.href = "/";
        } catch (error) {
          errorEl.textContent = "Unable to sign in. Try again.";
        }
      });

      signupForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        signupErrorEl.textContent = "";
        const formData = new FormData(signupForm);
        const email = String(formData.get("email") || "");
        const password = String(formData.get("password") || "");
        try {
          const response = await fetch("/api/auth/register", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password })
          });
          if (!response.ok) {
            const payload = await response.json().catch(() => ({}));
            signupErrorEl.textContent = payload.detail || "Unable to create account.";
            return;
          }
          window.location.href = "/";
        } catch (error) {
          signupErrorEl.textContent = "Unable to create account. Try again.";
        }
      });
    </script>
  </body>
</html>
"""


class LoginPayload(BaseModel):
    email: str
    password: str


class RegisterPayload(BaseModel):
    email: str
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
    if not session_token:
        return False
    session = db.get_session_user_by_token(
        DB_PATH,
        db.hash_session_token(session_token),
        int(time.time()),
    )
    return session is not None


def get_authenticated_user_id(request: Request) -> int:
    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    token_hash = db.hash_session_token(session_token)
    session = db.get_session_user_by_token(DB_PATH, token_hash, int(time.time()))
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    db.touch_session_expiry(DB_PATH, token_hash, int(time.time()) + SESSION_TTL_SECONDS)
    return int(session["user_id"])


def create_authenticated_response(user_id: int) -> Response:
    db.delete_expired_sessions(DB_PATH, int(time.time()))
    session_token = token_urlsafe(32)
    db.create_session(
        DB_PATH,
        user_id=user_id,
        token_hash=db.hash_session_token(session_token),
        expires_at=int(time.time()) + SESSION_TTL_SECONDS,
    )
    response = JSONResponse({"ok": True})
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_token,
        httponly=True,
        samesite="lax",
        secure=COOKIE_SECURE,
        path="/",
    )
    return response


def clear_session(request: Request, response: Response) -> None:
    session_token = request.cookies.get(SESSION_COOKIE_NAME, "")
    if session_token:
        db.delete_session_by_token(DB_PATH, db.hash_session_token(session_token))
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
    CONVERSATION_HISTORY.clear()
    db.init_database(DB_PATH, MVP_USERNAME, MVP_PASSWORD)


@app.post("/api/auth/register")
async def register(payload: RegisterPayload) -> Response:
    email = db.normalize_email(payload.email)
    password = payload.password
    if "@" not in email:
        raise HTTPException(status_code=400, detail="A valid email address is required")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Password must be at least {MIN_PASSWORD_LENGTH} characters",
        )
    user = db.create_user(DB_PATH, email, password)
    if user is None:
        raise HTTPException(status_code=409, detail="Email is already registered")
    return create_authenticated_response(int(user["id"]))


@app.post("/api/auth/login")
async def login(payload: LoginPayload) -> Response:
    user = db.get_user_by_email(DB_PATH, payload.email)
    if user is None:
        return JSONResponse(
            {"ok": False, "error": "Invalid credentials"}, status_code=401
        )
    is_valid, needs_rehash = db.verify_password(user["password_hash"], payload.password)
    if not is_valid:
        return JSONResponse(
            {"ok": False, "error": "Invalid credentials"}, status_code=401
        )
    user_id = int(user["id"])
    if needs_rehash:
        db.update_user_password(DB_PATH, user_id, payload.password)
    return create_authenticated_response(user_id)


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
def session(request: Request) -> dict:
    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_token:
        return {"authenticated": False, "user": None}
    token_hash = db.hash_session_token(session_token)
    row = db.get_session_user_by_token(DB_PATH, token_hash, int(time.time()))
    if row is None:
        return {"authenticated": False, "user": None}
    db.touch_session_expiry(DB_PATH, token_hash, int(time.time()) + SESSION_TTL_SECONDS)
    return {
        "authenticated": True,
        "user": {
            "id": int(row["user_id"]),
            "username": row["username"],
            "email": row["email"],
        },
    }


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
