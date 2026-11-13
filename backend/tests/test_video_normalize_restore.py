import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("BOBINE_DATABASE_URL", "sqlite:///data/test_database.db")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from app.api.routes import videos  # noqa: E402
from app.database import SessionLocal, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import ImportSource, Video  # noqa: E402


@pytest.fixture()
def video(tmp_path):
    init_db()
    source = tmp_path / "cours.mkv"
    source.write_bytes(b"original")
    with SessionLocal() as db:
        row = Video(title="Normalisation", file_path=str(source), duration_seconds=10, source=ImportSource.upload)
        db.add(row)
        db.commit()
        video_id = row.id
    yield video_id, source
    with SessionLocal() as db:
        db.query(Video).filter(Video.id == video_id).delete()
        db.commit()


def test_failed_normalization_puts_the_original_back(video, monkeypatch):
    video_id, source = video

    def fail(src, dest, actions, source_metadata=None):
        Path(dest).write_bytes(b"sortie partielle")
        raise RuntimeError("ffmpeg en échec")

    monkeypatch.setattr(videos, "normalize_video", fail)
    videos.bg_normalize(video_id, ["transcode_video"])
    assert source.read_bytes() == b"original"
    assert sorted(path.name for path in source.parent.iterdir()) == ["cours.mkv"]
    with SessionLocal() as db:
        assert db.get(Video, video_id).file_path == str(source)


def test_successful_normalization_replaces_the_file(video, monkeypatch):
    video_id, source = video
    monkeypatch.setattr(videos, "normalize_video", lambda src, dest, actions, source_metadata=None: Path(dest).write_bytes(b"mp4"))
    monkeypatch.setattr(videos, "extract_metadata", lambda path: {"duration_seconds": 12, "width": 1920, "height": 1080, "codec": "h264"})
    monkeypatch.setattr(videos, "generate_thumbnail", lambda path, folder, duration: None)
    videos.bg_normalize(video_id, ["transcode_video"])
    with SessionLocal() as db:
        row = db.get(Video, video_id)
        assert Path(row.file_path).read_bytes() == b"mp4" and row.duration_seconds == 12
    assert [path.suffix for path in source.parent.iterdir()] == [".mp4"]


def test_oversized_thumbnail_is_refused_not_a_server_error(video, monkeypatch, tmp_path):
    video_id, _ = video
    picture = tmp_path / "grande.png"
    Image.new("RGB", (64, 64)).save(picture)
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 100)
    with picture.open("rb") as handle:
        answer = TestClient(app).put(f"/api/videos/{video_id}/thumbnail", files={"file": ("grande.png", handle, "image/png")})
    assert answer.status_code == 422
