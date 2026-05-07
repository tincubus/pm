from fastapi.testclient import TestClient

from app.main import app
import app.main as main_module


def setup_paths(tmp_path, monkeypatch):
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<h1>Kanban Studio</h1>", encoding="utf-8")
    monkeypatch.setattr(main_module, "STATIC_DIR", static_dir)

    db_path = tmp_path / "data" / "pm.db"
    monkeypatch.setattr(main_module, "DB_PATH", db_path)


def login(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        json={"username": "user", "password": "password"},
    )
    assert response.status_code == 200


def test_ai_smoke_requires_auth(tmp_path, monkeypatch):
    setup_paths(tmp_path, monkeypatch)
    with TestClient(app) as client:
        response = client.post("/api/ai/smoke")
        assert response.status_code == 401


def test_ai_smoke_returns_model_answer(tmp_path, monkeypatch):
    setup_paths(tmp_path, monkeypatch)

    monkeypatch.setattr(main_module.ai, "run_smoke_test", lambda: "4")
    with TestClient(app) as client:
        login(client)
        response = client.post("/api/ai/smoke")
        assert response.status_code == 200
        payload = response.json()
        assert payload["ok"] is True
        assert payload["model"] == "openai/gpt-oss-120b"
        assert payload["response"] == "4"


def test_ai_smoke_handles_missing_key(tmp_path, monkeypatch):
    setup_paths(tmp_path, monkeypatch)

    def raise_missing_key():
        raise ValueError("OPENROUTER_API_KEY is missing")

    monkeypatch.setattr(main_module.ai, "run_smoke_test", raise_missing_key)

    with TestClient(app) as client:
        login(client)
        response = client.post("/api/ai/smoke")
        assert response.status_code == 503
        assert "OPENROUTER_API_KEY is missing" in response.json()["detail"]
