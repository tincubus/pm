from fastapi.testclient import TestClient

from app import ai_chat
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


def test_structured_parser_accepts_valid_json():
    parsed = ai_chat.parse_structured_response(
        """
        {
          "assistant_response": "Done",
          "board_update": {
            "rename_columns": [],
            "create_cards": [],
            "update_cards": [],
            "move_cards": [],
            "delete_cards": []
          }
        }
        """
    )
    assert parsed.assistant_response == "Done"
    assert parsed.board_update is not None


def test_structured_parser_rejects_invalid_payload():
    try:
        ai_chat.parse_structured_response("not-json")
    except ValueError:
        assert True
        return
    assert False, "expected ValueError for invalid AI payload"


def test_ai_chat_requires_auth(tmp_path, monkeypatch):
    setup_paths(tmp_path, monkeypatch)
    with TestClient(app) as client:
        response = client.post("/api/ai/chat", json={"message": "hi"})
        assert response.status_code == 401


def test_ai_chat_applies_board_updates(tmp_path, monkeypatch):
    setup_paths(tmp_path, monkeypatch)

    response_json = """
    {
      "assistant_response": "I added the card.",
      "board_update": {
        "rename_columns": [],
        "create_cards": [{"column_id": 1, "title": "AI Created", "details": "From AI"}],
        "update_cards": [],
        "move_cards": [],
        "delete_cards": []
      }
    }
    """
    monkeypatch.setattr(main_module.ai, "send_chat_messages_with_env", lambda _messages: response_json)

    with TestClient(app) as client:
        login(client)
        response = client.post("/api/ai/chat", json={"message": "add card"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["ok"] is True
        assert payload["parse_error"] is False
        assert any("created card" in op for op in payload["applied_operations"])
        assert any(card["title"] == "AI Created" for card in payload["board"]["cards"].values())


def test_ai_chat_handles_invalid_structured_output(tmp_path, monkeypatch):
    setup_paths(tmp_path, monkeypatch)
    monkeypatch.setattr(main_module.ai, "send_chat_messages_with_env", lambda _messages: "bad-output")

    with TestClient(app) as client:
        login(client)
        response = client.post("/api/ai/chat", json={"message": "do something"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["ok"] is True
        assert payload["parse_error"] is True
        assert payload["applied_operations"] == []


def test_ai_chat_uses_in_memory_conversation_history(tmp_path, monkeypatch):
    setup_paths(tmp_path, monkeypatch)
    captured_messages: list[list[dict[str, str]]] = []

    def fake_send(messages: list[dict[str, str]]) -> str:
        captured_messages.append(messages)
        return """
        {
          "assistant_response": "ok",
          "board_update": null
        }
        """

    monkeypatch.setattr(main_module.ai, "send_chat_messages_with_env", fake_send)

    with TestClient(app) as client:
        login(client)
        first = client.post("/api/ai/chat", json={"message": "first"})
        second = client.post("/api/ai/chat", json={"message": "second"})
        assert first.status_code == 200
        assert second.status_code == 200

    assert len(captured_messages) == 2
    second_call = captured_messages[1]
    serialized = " ".join(item["content"] for item in second_call)
    assert "first" in serialized
    assert "ok" in serialized
