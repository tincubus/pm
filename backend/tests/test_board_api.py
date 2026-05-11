from fastapi.testclient import TestClient

from app.main import app
import app.main as main_module


def login(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        json={"email": "user@local.pm", "password": "password"},
    )
    assert response.status_code == 200


def setup_paths(tmp_path, monkeypatch):
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<h1>Kanban Studio</h1>", encoding="utf-8")
    monkeypatch.setattr(main_module, "STATIC_DIR", static_dir)

    db_path = tmp_path / "data" / "pm.db"
    monkeypatch.setattr(main_module, "DB_PATH", db_path)
    return db_path


def test_creates_db_if_missing(tmp_path, monkeypatch):
    db_path = setup_paths(tmp_path, monkeypatch)
    assert not db_path.exists()

    with TestClient(app):
        pass

    assert db_path.exists()


def test_board_api_requires_auth(tmp_path, monkeypatch):
    setup_paths(tmp_path, monkeypatch)
    with TestClient(app) as client:
        response = client.get("/api/board")
        assert response.status_code == 401


def test_board_api_read_and_update_flow(tmp_path, monkeypatch):
    setup_paths(tmp_path, monkeypatch)
    with TestClient(app) as client:
        login(client)

        board_response = client.get("/api/board")
        assert board_response.status_code == 200
        board = board_response.json()
        assert len(board["columns"]) == 5
        assert len(board["cards"]) >= 8

        first_column = board["columns"][0]
        second_column = board["columns"][1]
        first_column_id = first_column["id"]
        second_column_id = second_column["id"]

        rename_response = client.patch(
            f"/api/columns/{first_column_id}",
            json={"title": "Ideas"},
        )
        assert rename_response.status_code == 200
        assert rename_response.json()["ok"] is True

        add_response = client.post(
            f"/api/columns/{first_column_id}/cards",
            json={"title": "New API card", "details": "Created by backend test"},
        )
        assert add_response.status_code == 200
        new_card_id = add_response.json()["card"]["id"]

        edit_response = client.patch(
            f"/api/cards/{new_card_id}",
            json={"title": "Renamed API card", "details": "Edited details"},
        )
        assert edit_response.status_code == 200
        assert edit_response.json()["card"]["title"] == "Renamed API card"

        move_response = client.post(
            f"/api/cards/{new_card_id}/move",
            json={"target_column_id": second_column_id, "target_position": 0},
        )
        assert move_response.status_code == 200
        assert move_response.json()["ok"] is True

        board_after_move = client.get("/api/board").json()
        second_column_after = next(
            column
            for column in board_after_move["columns"]
            if column["id"] == second_column_id
        )
        assert second_column_after["cardIds"][0] == new_card_id
        assert board_after_move["cards"][str(new_card_id)]["title"] == "Renamed API card"

        delete_response = client.delete(f"/api/cards/{new_card_id}")
        assert delete_response.status_code == 200
        assert delete_response.json()["ok"] is True

        board_after_delete = client.get("/api/board").json()
        assert str(new_card_id) not in board_after_delete["cards"]
