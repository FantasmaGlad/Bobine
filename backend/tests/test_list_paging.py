import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("BOBINE_DATABASE_URL", "sqlite:///data/test_database.db")

from fastapi.testclient import TestClient  # noqa: E402

from app.database import SessionLocal, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Playlist  # noqa: E402

LISTS = ("/api/videos", "/api/playlists", "/api/schedule", "/api/backgrounds", "/api/audio", "/api/audio/tracks",
         "/api/audio-playlists", "/api/radio/tracks", "/api/radio/playlists", "/api/radio/announcements",
         "/api/radio/announcement-rules", "/api/import-jobs")


def _playlists(count):
    init_db()
    with SessionLocal() as db:
        rows = [Playlist(name=f"Pagination {n:02d}") for n in range(count)]
        db.add_all(rows)
        db.commit()
        return [row.id for row in rows]


def test_lists_are_whole_without_window():
    client = TestClient(app)
    for path in LISTS:
        answer = client.get(path)
        assert answer.status_code == 200 and isinstance(answer.json(), list), path
        assert "x-total-count" not in answer.headers, path


def test_window_pages_and_counts():
    ids = _playlists(5)
    try:
        client = TestClient(app)
        whole = [p["id"] for p in client.get("/api/playlists").json()]
        answer = client.get("/api/playlists", params={"limit": 2, "offset": 1})
        assert [p["id"] for p in answer.json()] == whole[1:3]
        assert answer.headers["x-total-count"] == str(len(whole))
        assert client.get("/api/playlists", params={"limit": 0}).status_code == 422
        assert client.get("/api/playlists", params={"limit": 2, "offset": 10**30}).status_code == 422
        assert client.get("/api/metrics/ratings", params={"limit": -1}).status_code == 422
    finally:
        with SessionLocal() as db:
            db.query(Playlist).filter(Playlist.id.in_(ids)).delete()
            db.commit()


def test_every_list_accepts_a_window():
    client = TestClient(app)
    for path in LISTS:
        answer = client.get(path, params={"limit": 1})
        assert answer.status_code == 200 and len(answer.json()) <= 1, path
        assert answer.headers["x-total-count"].isdigit(), path
