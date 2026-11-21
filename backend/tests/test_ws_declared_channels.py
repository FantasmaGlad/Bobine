import os

os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_database.db"
os.environ["BOBINE_MEDIA_DIR"] = "data/test_videos"
os.environ["BOBINE_WATCH_DIR"] = "data/test_watched"
os.environ["BOBINE_THUMBNAILS_DIR"] = "data/test_thumbnails"

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def _initial_syncs(ws) -> list[str]:
    ws.send_json({"command": "time_sync", "params": {"t0": 1}})
    channels = []
    message = ws.receive_json()
    while message.get("event") != "time_sync":
        if message.get("event") == "state_change" and message.get("cause") == "sync":
            channels.append(message["channel"])
        message = ws.receive_json()
    return channels


def test_a_client_declaring_no_channel_receives_no_radio_state(client):
    with client.websocket_connect("/ws/playback?channels=") as ws:
        assert sorted(_initial_syncs(ws)) == ["cable", "network"]


def test_a_client_declaring_one_radio_receives_only_that_radio(client):
    with client.websocket_connect("/ws/playback?channels=radio_cable,inconnu") as ws:
        assert sorted(_initial_syncs(ws)) == ["cable", "network", "radio_cable"]


def test_the_legacy_alias_declares_the_network_radio(client):
    with client.websocket_connect("/ws/playback?channels=radio") as ws:
        assert sorted(_initial_syncs(ws)) == ["cable", "network", "radio_network"]


def test_a_client_declaring_nothing_keeps_every_state(client):
    with client.websocket_connect("/ws/playback") as ws:
        assert sorted(_initial_syncs(ws)) == ["cable", "network", "radio_cable", "radio_network"]
