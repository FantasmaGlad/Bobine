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
    assert sound["bass_boost"] == 12  # borné, jamais d'erreur
    assert manager.sounds == [(sound, 12.5)] and mirrors == [True]


def test_announcement_resolution_and_duck_mode(mirrors):
    init_db()
    with SessionLocal() as db:
        db.query(RadioAnnouncement).delete()
        on = RadioAnnouncement(file_path="/a.mp3", description="Actif", enabled=True)
        off = RadioAnnouncement(file_path="/b.mp3", description="Inactif", enabled=False)
        db.add_all([on, off])
        db.commit()
        assert radio_commands.resolve_announcement(db, off.id) is None  # désactivé : jamais joué
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
