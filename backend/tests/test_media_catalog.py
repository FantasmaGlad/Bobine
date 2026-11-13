import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("BOBINE_DATABASE_URL", "sqlite:///data/test_database.db")

from fastapi.testclient import TestClient  # noqa: E402

from app.api import contract  # noqa: E402
from app.catalog.entries import LOADERS  # noqa: E402
from app.database import SessionLocal, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import ImportSource, Playlist, PlaylistItem, Video  # noqa: E402


def _seed():
    init_db()
    with SessionLocal() as db:
        video = Video(file_path="data/test_videos/catalog_a.mp4", title="Échauffement Énergie", duration_seconds=600.0,
                      source=ImportSource.upload, program="BODYPUMP")
        db.add(video)
        db.flush()
        playlist = Playlist(name="Catalogue du soir")
        db.add(playlist)
        db.flush()
        db.add(PlaylistItem(playlist_id=playlist.id, video_id=video.id, position=0))
        db.commit()
        return video.id, playlist.id


def _cleanup(video_id, playlist_id):
    with SessionLocal() as db:
        db.query(PlaylistItem).filter(PlaylistItem.playlist_id == playlist_id).delete()
        db.query(Playlist).filter(Playlist.id == playlist_id).delete()
        db.query(Video).filter(Video.id == video_id).delete()
        db.commit()


def test_every_media_kind_has_a_loader():
    assert tuple(LOADERS) == contract.MEDIA_KINDS
    assert set(contract.PLAYABLE_MEDIA) <= set(contract.MEDIA_KINDS)


def test_catalog_lists_searches_and_pages():
    video_id, playlist_id = _seed()
    try:
        client = TestClient(app)
        found = client.get("/api/media", params={"q": "echauffement energie"}).json()
        assert [(e["kind"], e["id"]) for e in found["items"]] == [("video", video_id)]
        assert found["items"][0]["subtitle"] == "BODYPUMP"
        playlists = client.get("/api/media", params={"kind": "playlist", "q": "catalogue"}).json()["items"]
        assert playlists[0]["id"] == playlist_id and playlists[0]["duration_seconds"] == 600.0
        page = client.get("/api/media", params={"limit": 1, "offset": 0}).json()
        assert len(page["items"]) == 1 and page["total"] >= 2 and page["limit"] == 1
    finally:
        _cleanup(video_id, playlist_id)


def test_unknown_kind_is_invalid():
    answer = TestClient(app).get("/api/media", params={"kind": "cassette"})
    assert answer.status_code == 422 and answer.json()["detail"]["code"] == "invalid"
