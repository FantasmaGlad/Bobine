import os
from datetime import datetime, timedelta, timezone

os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_database.db"
os.environ["BOBINE_MEDIA_DIR"] = "data/test_videos"
os.environ["BOBINE_WATCH_DIR"] = "data/test_watched"
os.environ["BOBINE_THUMBNAILS_DIR"] = "data/test_thumbnails"

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import ImportSource, Schedule, Video
from app.scheduling.occurrences import ensure_utc

PARIS_WINTER = timezone(timedelta(hours=1))


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def video_id():
    db = SessionLocal()
    try:
        video = Video(file_path="/seed/timezone.mp4", title="Cours", source=ImportSource.upload, duration_seconds=60.0)
        db.add(video)
        db.commit()
        yield video.id
        db.query(Schedule).filter(Schedule.target_id == video.id).delete()
        db.delete(db.get(Video, video.id))
        db.commit()
    finally:
        db.close()


def test_ensure_utc_converts_an_offset_instead_of_dropping_it():
    local = datetime(2026, 11, 22, 20, 0, tzinfo=PARIS_WINTER)
    assert ensure_utc(local) == local
    assert ensure_utc(local).utcoffset() == timedelta(0)
    assert ensure_utc(datetime(2026, 11, 22, 19, 0)) == datetime(2026, 11, 22, 19, 0, tzinfo=timezone.utc)


def test_a_once_schedule_keeps_the_instant_given_with_an_offset(client, video_id):
    wanted = (datetime.now(PARIS_WINTER) + timedelta(days=2)).replace(hour=20, minute=0, second=0, microsecond=0)
    response = client.post("/api/schedule", json={
        "target_type": "video", "target_id": video_id, "schedule_type": "once", "run_at": wanted.isoformat(), "channel": "cable",
    })
    assert response.status_code == 200
    created = response.json()
    assert datetime.fromisoformat(created["run_at"]) == wanted
    stored = client.get(f"/api/schedule/{created['id']}").json()
    assert datetime.fromisoformat(stored["run_at"]) == wanted
