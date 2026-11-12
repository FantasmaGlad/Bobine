"""Son radio et rappel immédiat : un seul code pour REST, WebSocket et CLI."""
import asyncio
import os

os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_database.db"
os.environ["BOBINE_MEDIA_DIR"] = "data/test_videos"
os.environ["BOBINE_WATCH_DIR"] = "data/test_watched"
os.environ["BOBINE_THUMBNAILS_DIR"] = "data/test_thumbnails"

import pytest
from fastapi.testclient import TestClient

from app import config_files
from app.database import SessionLocal, init_db
from app.main import app
from app.models import RadioAnnouncement
from app.utils import radio_commands


class FakeManager:
    channel = "radio_cable"

    def __init__(self):
        self.state = {"sound": {}}
        self.sounds, self.played = [], []

    async def set_sound(self, sound, client_ts=None):
        self.sounds.append((sound, client_ts))

    async def play_announcement(self, payload, mode, client_ts=None):
        self.played.append((payload, mode, client_ts))


@pytest.fixture()
def mirrors(monkeypatch):
    calls = []
    monkeypatch.setattr(config_files, "schedule_mirror", lambda: calls.append(True))
    return calls


def test_sound_is_bounded_saved_broadcast_and_mirrored(mirrors):
    init_db()
    manager = FakeManager()
    with SessionLocal() as db:
        sound = asyncio.run(radio_commands.apply_sound(db, manager, {"bass_boost": 9999}, 12.5))
    assert sound["bass_boost"] == 12
    assert manager.sounds == [(sound, 12.5)] and mirrors == [True]


def test_announcement_resolution_and_duck_mode(mirrors):
    init_db()
    with SessionLocal() as db:
        db.query(RadioAnnouncement).delete()
        on = RadioAnnouncement(file_path="/a.mp3", description="Actif", enabled=True)
        off = RadioAnnouncement(file_path="/b.mp3", description="Inactif", enabled=False)
        db.add_all([on, off])
        db.commit()
        assert radio_commands.resolve_announcement(db, off.id) is None
        assert radio_commands.resolve_announcement(db, None).id == on.id
        manager = FakeManager()
        payload = asyncio.run(radio_commands.play_announcement_now(db, [manager, FakeManager()], on, 3.0))
        assert payload == {"id": on.id, "description": "Actif"} and manager.played == [(payload, "duck", 3.0)]
        db.query(RadioAnnouncement).delete()
        db.commit()


def test_rest_routes_use_the_shared_code():
    init_db()
    client = TestClient(app)
    assert client.put("/api/radio/sound?channel=radio_cable", json={"bass_boost": 4}).status_code == 200
    assert client.post("/api/radio/announcements/play-now", json={}).status_code in (200, 404)


def test_put_sound_and_the_facade_give_the_same_state_and_persistence():
    """`PUT /api/radio/sound` et `POST /api/radio/{sortie}/radio_set_sound` : mêmes bornes, même état, même copie en base."""
    from app.radio_manager import get_radio_manager
    from app.utils.radio_sound import load_sound

    init_db()
    with TestClient(app) as client:
        manager = get_radio_manager("radio_network")
        put = client.put("/api/radio/sound?channel=radio_network", json={"bass_boost": 99, "bands": [50, 0, 0, 0, -50]})
        assert put.status_code == 200
        via_put = put.json()
        manager.state["sound"] = {**via_put, "bass_boost": 0, "bands": [0] * 5}
        facade = client.post("/api/radio/network/radio_set_sound", json={"sound": {"bass_boost": 99, "bands": [50, 0, 0, 0, -50]}})
        assert facade.status_code == 200
        via_facade = facade.json()["state"]["sound"]
        assert via_put == via_facade and via_put["bass_boost"] == 12 and via_put["bands"] == [12, 0, 0, 0, -12]
        with SessionLocal() as db:
            assert load_sound(db, "radio_network") == via_put


def test_play_now_and_the_facade_reach_the_same_players():
    """Le rappel immédiat par REST, par la façade et par la commande WebSocket arrive aux mêmes sorties, en « duck »."""
    from app.radio_manager import get_radio_manager

    init_db()
    with SessionLocal() as db:
        db.query(RadioAnnouncement).delete()
        announcement = RadioAnnouncement(file_path="/a.mp3", description="Actif", enabled=True)
        db.add(announcement)
        db.commit()
        announcement_id = announcement.id
    seen = []

    async def record(payload, mode="duck", client_ts=None):
        seen.append((payload["id"], mode))

    managers = [get_radio_manager("radio_cable"), get_radio_manager("radio_network")]
    originals = [m.play_announcement for m in managers]
    for manager in managers:
        manager.play_announcement = record
    try:
        with TestClient(app) as client:
            assert client.post("/api/radio/announcements/play-now", json={"announcement_id": announcement_id, "target": "radio_network"}).status_code == 200
            assert client.post("/api/radio/network/radio_play_announcement", json={"announcement_id": announcement_id}).status_code == 200
    finally:
        for manager, original in zip(managers, originals):
            manager.play_announcement = original
        with SessionLocal() as db:
            db.query(RadioAnnouncement).delete()
            db.commit()
    assert seen == [(announcement_id, "duck"), (announcement_id, "duck")]
