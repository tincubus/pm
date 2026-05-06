from fastapi.testclient import TestClient

from app.main import app
import app.main as main_module


def test_requires_login_for_root(tmp_path, monkeypatch):
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<h1>Kanban Studio</h1>", encoding="utf-8")
    monkeypatch.setattr(main_module, "STATIC_DIR", static_dir)

    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    assert "Sign in" in response.text


def test_login_logout_flow_and_session(tmp_path, monkeypatch):
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<h1>Kanban Studio</h1>", encoding="utf-8")
    monkeypatch.setattr(main_module, "STATIC_DIR", static_dir)

    client = TestClient(app)

    bad_login = client.post(
        "/api/auth/login", json={"username": "wrong", "password": "creds"}
    )
    assert bad_login.status_code == 401
    assert bad_login.json()["ok"] is False

    good_login = client.post(
        "/api/auth/login", json={"username": "user", "password": "password"}
    )
    assert good_login.status_code == 200
    assert good_login.json()["ok"] is True
    assert "pm_session" in good_login.headers.get("set-cookie", "")

    session_response = client.get("/api/auth/session")
    assert session_response.status_code == 200
    assert session_response.json()["authenticated"] is True

    root_response = client.get("/")
    assert root_response.status_code == 200
    assert "Kanban Studio" in root_response.text

    logout_response = client.post("/api/auth/logout")
    assert logout_response.status_code == 200
    assert logout_response.json()["ok"] is True

    session_after_logout = client.get("/api/auth/session")
    assert session_after_logout.status_code == 200
    assert session_after_logout.json()["authenticated"] is False

    root_after_logout = client.get("/")
    assert root_after_logout.status_code == 200
    assert "Sign in" in root_after_logout.text
