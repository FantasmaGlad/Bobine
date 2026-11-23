import os

os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_database.db"
os.environ["BOBINE_MEDIA_DIR"] = "data/test_videos"
os.environ["BOBINE_WATCH_DIR"] = "data/test_watched"
os.environ["BOBINE_THUMBNAILS_DIR"] = "data/test_thumbnails"

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.playback.manager import get_playback_manager
from app.radio.manager import get_radio_manager


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_a_seek_with_an_unknown_key_is_refused_and_moves_nothing(client):
    manager = get_playback_manager("cable")
    manager.state["position_seconds"] = 42.0
    response = client.post("/api/outputs/cable/playback/seek", json={"position": 120})
    assert response.status_code == 422
    assert "position_seconds" in response.text
    assert manager.state["position_seconds"] == 42.0


@pytest.mark.parametrize("body", [{}, {"volume": "fort"}, {"volume": True}, {"volume": -5}])
def test_a_volume_without_a_valid_number_is_refused(client, body):
    manager = get_playback_manager("cable")
    manager.state["volume"] = 37
    assert client.post("/api/outputs/cable/playback/volume", json=body).status_code == 422
    assert manager.state["volume"] == 37


def test_a_radio_seek_without_position_is_refused(client):
    assert client.post("/api/outputs/cable/radio/radio_seek", json={"position": 30}).status_code == 422


def test_the_websocket_reports_the_refusal(client):
    manager = get_radio_manager("radio_cable")
    manager.state["volume"] = 64
    with client.websocket_connect("/ws/playback?channels=") as ws:
        ws.send_json({"command": "volume", "params": {"channel": "radio_cable"}})
        message = ws.receive_json()
        while message.get("event") != "command_rejected":
            message = ws.receive_json()
    assert message["reason"] == "invalid_params"
    assert manager.state["volume"] == 64
