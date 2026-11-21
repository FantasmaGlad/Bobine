import io
import os

os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_database.db"
os.environ["BOBINE_MEDIA_DIR"] = "data/test_videos"
os.environ["BOBINE_WATCH_DIR"] = "data/test_watched"
os.environ["BOBINE_THUMBNAILS_DIR"] = "data/test_thumbnails"

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.database import SessionLocal
from app.main import app
from app.models import ImportSource, Video
from app.utils.ws_manager import manager as ws_manager

VTT = b"WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nBonjour\n"


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def video_id():
    db = SessionLocal()
    try:
        video = Video(file_path="/seed/library-change.mp4", title="Cours", source=ImportSource.upload, duration_seconds=60.0)
        db.add(video)
        db.commit()
        yield video.id
        db.delete(db.get(Video, video.id))
        db.commit()
    finally:
        db.close()


@pytest.fixture
def notices(monkeypatch):
    sent = []
    monkeypatch.setattr(ws_manager, "broadcast_threadsafe", lambda message: sent.append(message))
    return sent


def _png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), "red").save(buffer, "PNG")
    return buffer.getvalue()


def test_chapter_subtitle_and_thumbnail_changes_reach_the_screens(client, video_id, notices):
    assert client.put(f"/api/videos/{video_id}/chapters", json={"chapters": [{"start_seconds": 0, "title": "Échauffement"}]}).status_code == 200
    subtitle = client.post(f"/api/videos/{video_id}/subtitles", files={"file": ("fr.vtt", VTT, "text/vtt")}, data={"language_code": "fr"})
    assert subtitle.status_code == 200
    assert client.delete(f"/api/videos/{video_id}/subtitles/{subtitle.json()['id']}").status_code == 200
    assert client.put(f"/api/videos/{video_id}/thumbnail", files={"file": ("t.png", _png(), "image/png")}).status_code == 200
    assert [n.get("event") for n in notices] == ["library_change"] * 4
    assert [n["reason"] for n in notices] == ["chapters_changed", "subtitles_changed", "subtitles_changed", "thumbnail_changed"]
