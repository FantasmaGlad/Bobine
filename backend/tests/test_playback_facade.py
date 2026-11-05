"""Façade REST de la lecture : mêmes commandes et même effet que le WebSocket, refus typés au lieu d'un silence,
rapports d'écran exclus, routes existantes de même forme non masquées ; une commande en échec ne coupe plus la
connexion WebSocket."""

import asyncio
import os

os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_database.db"
os.environ["BOBINE_MEDIA_DIR"] = "data/test_videos"
os.environ["BOBINE_WATCH_DIR"] = "data/test_watched"
os.environ["BOBINE_THUMBNAILS_DIR"] = "data/test_thumbnails"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import RadioTrack, Setting  # noqa: E402
from app.playback_manager import get_playback_manager  # noqa: E402
from app.radio_manager import get_radio_manager  # noqa: E402
from app.routers.playback import PLAYBACK_ACTIONS, RADIO_ACTIONS  # noqa: E402

OUTPUT_KEYS = ("display_output_cable", "display_output_network")


def _reset():
    db = SessionLocal()
    try:
        db.query(Setting).filter(Setting.key.in_(OUTPUT_KEYS)).delete(synchronize_session=False)
        db.query(RadioTrack).delete()
        db.commit()
    finally:
        db.close()
    for channel in ("cable", "network"):
        asyncio.run(get_playback_manager(channel).stop())
    for channel in ("radio_cable", "radio_network"):
        asyncio.run(get_radio_manager(channel).stop())


@pytest.fixture()
def client():
    with TestClient(app) as c:
        _reset()
        yield c
        _reset()


def _without_clocks(state):
    """L'horodatage des horloges change à chaque instantané : seul le reste de l'état se compare."""
    return {key: value for key, value in state.items() if key not in ("clock", "audio_clock")}


def _receive_until(ws, event):
    for _ in range(50):
        message = ws.receive_json()
        if message.get("event") == event:
            return message
    raise AssertionError(f"évènement {event} jamais reçu")


def test_rest_and_websocket_reach_the_same_state(client):
    answer = client.post("/api/playback/network/volume", json={"volume": 37})
    assert answer.status_code == 200
    assert answer.json()["state"]["volume"] == 37 == get_playback_manager("network").snapshot()["volume"]
    with client.websocket_connect("/ws/playback") as ws:
        ws.send_json({"command": "volume", "params": {"channel": "network", "volume": 64}})
        _receive_until(ws, "state_change")
    after_websocket = _without_clocks(get_playback_manager("network").snapshot())
    assert _without_clocks(client.post("/api/playback/network/volume", json={"volume": 64}).json()["state"]) == after_websocket


def test_radio_output_command(client):
    answer = client.post("/api/radio/network/volume", json={"volume": 42})
    assert answer.status_code == 200
    assert answer.json()["state"]["volume"] == 42 == get_radio_manager("radio_network").snapshot()["volume"]
    assert client.post("/api/radio/cable/radio_set_repeat", json={"mode": "track"}).json()["state"]["repeat"] == "track"


def test_typed_refusals(client):
    missing = client.post("/api/playback/cable/load", json={"video_id": 987654})
    assert missing.status_code == 404 and missing.json()["detail"]["code"] == "not_found"
    bad = client.post("/api/playback/cable/seek", json={"position_seconds": "pas un nombre"})
    assert bad.status_code == 422 and bad.json()["detail"]["code"] == "invalid_params"
    coach = client.post("/api/playback/network/load_audio_course", json={"audio_course_id": 1})
    assert coach.status_code == 409 and coach.json()["detail"]["code"] == "coach_cable_only"
    empty = client.post("/api/radio/network/radio_shuffle_all")
    assert empty.status_code == 409 and empty.json()["detail"]["code"] == "empty_library"


def test_locked_channel_is_refused_on_both_transports(client):
    assert client.put("/api/settings/display-output", json={"channel": "cable", "output": "radio"}).status_code == 200
    locked = client.post("/api/playback/cable/load", json={"video_id": 1})
    assert locked.status_code == 409 and locked.json()["detail"]["code"] == "radio_locked"
    with client.websocket_connect("/ws/playback") as ws:
        ws.send_json({"command": "load", "params": {"channel": "cable", "video_id": 1}})
        assert _receive_until(ws, "command_rejected")["reason"] == "radio_locked"


def test_unknown_targets_and_screen_reports_are_not_exposed(client):
    assert client.post("/api/playback/salle/play").json()["detail"]["code"] == "unknown_channel"
    assert client.post("/api/radio/salle/play").json()["detail"]["code"] == "unknown_output"
    for action in ("report_position", "video_ended", "radio_report_levels", "identify"):
        answer = client.post(f"/api/playback/cable/{action}")
        assert answer.status_code == 404 and answer.json()["detail"]["code"] == "unknown_action"
    assert "report_position" not in PLAYBACK_ACTIONS and "radio_track_ended" not in RADIO_ACTIONS


def test_existing_radio_routes_are_not_masked(client):
    answer = client.post("/api/radio/announcements/play-now", json={})
    assert not (answer.status_code == 404 and isinstance(answer.json().get("detail"), dict)
                and answer.json()["detail"].get("code") == "unknown_action")


def test_a_failing_command_keeps_the_websocket_open(client):
    with client.websocket_connect("/ws/playback") as ws:
        ws.send_json({"command": "seek", "params": {"channel": "cable", "position_seconds": "pas un nombre"}})
        assert _receive_until(ws, "command_rejected")["reason"] == "invalid_params"
        ws.send_json({"command": "volume", "params": {"channel": "cable", "volume": 55}})
        assert _receive_until(ws, "state_change")["data"]["volume"] == 55
