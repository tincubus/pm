from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

app = FastAPI(title="PM MVP Backend")

STATIC_DIR = Path(__file__).resolve().parent / "static"
SESSION_COOKIE_NAME = "pm_session"
SESSION_COOKIE_VALUE = "authenticated"
MVP_USERNAME = "user"
MVP_PASSWORD = "password"

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


def is_authenticated(request: Request) -> bool:
    return request.cookies.get(SESSION_COOKIE_NAME) == SESSION_COOKIE_VALUE


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


@app.post("/api/auth/login")
async def login(payload: dict[str, str]) -> Response:
    username = payload.get("username", "")
    password = payload.get("password", "")
    if username != MVP_USERNAME or password != MVP_PASSWORD:
        return JSONResponse(
            {"ok": False, "error": "Invalid credentials"}, status_code=401
        )
    response = JSONResponse({"ok": True})
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=SESSION_COOKIE_VALUE,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )
    return response


@app.post("/api/auth/logout")
def logout() -> Response:
    response = JSONResponse({"ok": True})
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return response


@app.get("/api/auth/session")
def session(request: Request) -> dict[str, bool]:
    return {"authenticated": is_authenticated(request)}


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
