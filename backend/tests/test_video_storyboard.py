import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("BOBINE_DATABASE_URL", "sqlite:///data/test_database.db")

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal, init_db
from app.main import app
from app.models import ImportSource, Video
from app.videos import storyboard
from app.videos.storyboard_layout import storyboard_layout


@pytest.fixture()
def video_id(tmp_path):
    init_db()
    source = tmp_path / "cours.mp4"
    source.write_bytes(b"video")
    with SessionLocal() as db:
        row = Video(title="Aperçu", file_path=str(source), duration_seconds=95.0, source=ImportSource.upload)
        db.add(row)
        db.commit()
        identifier = row.id
    yield identifier
    with SessionLocal() as db:
        db.query(Video).filter(Video.id == identifier).delete()
        db.commit()


def test_layout_one_tile_every_ten_seconds_for_short_videos():
    layout = storyboard_layout(95)
    assert (layout.interval_seconds, layout.count, layout.columns, layout.rows, layout.sheets) == (10, 10, 10, 1, 1)
    assert (layout.tile_width, layout.tile_height) == (320, 180)


def test_layout_caps_long_videos_at_240_tiles():
    layout = storyboard_layout(3230.2)
    assert layout.interval_seconds == 14
    assert layout.count == 231
    assert (layout.columns, layout.rows, layout.sheets) == (10, 10, 3)


def test_layout_needs_a_duration():
    assert storyboard_layout(None) is None
    assert storyboard_layout(0) is None
    assert storyboard_layout(3).count == 1


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg absent")
def test_generated_mosaic_has_the_layout_size(tmp_path, monkeypatch):
    from PIL import Image

    source = tmp_path / "clip.mp4"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=25",
                    "-t", "35", "-g", "25", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source)], check=True)
    monkeypatch.setattr(storyboard.settings, "thumbnails_dir", str(tmp_path / "thumbs"))
    assert storyboard.generate_storyboard(7, str(source), 35.0)
    with Image.open(storyboard.sheet_path(7, 0)) as img:
        assert img.size == (4 * 320, 1 * 180)
    assert not storyboard.is_stale(7, str(source))


def test_failed_generation_leaves_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr(storyboard.settings, "thumbnails_dir", str(tmp_path / "thumbs"))
    source = tmp_path / "broken.mp4"
    source.write_bytes(b"not a video")
    assert not storyboard.generate_storyboard(8, str(source), 40.0)
    assert not storyboard.storyboard_dir(8).exists()
    assert not list((tmp_path / "thumbs" / "storyboards").glob("*"))


def test_route_answers_404_until_the_mosaic_exists(video_id, tmp_path, monkeypatch):
    monkeypatch.setattr(storyboard.settings, "thumbnails_dir", str(tmp_path / "thumbs"))
    client = TestClient(app)
    response = client.get(f"/api/videos/{video_id}/storyboard")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "storyboard_not_ready"
    path = storyboard.sheet_path(video_id, 0)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"jpg")
    body = client.get(f"/api/videos/{video_id}/storyboard").json()
    assert [s.split("?")[0] for s in body["sheets"]] == [f"/api/thumbnails/storyboards/{video_id}/sheet-0.jpg"]
    assert (body["interval_seconds"], body["count"], body["columns"], body["rows"]) == (10, 10, 10, 1)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg absent")
def test_a_video_shorter_than_the_interval_gets_its_single_tile(tmp_path, monkeypatch):
    from PIL import Image

    source = tmp_path / "short.mp4"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=30",
                    "-t", "3", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source)], check=True)
    monkeypatch.setattr(storyboard.settings, "thumbnails_dir", str(tmp_path / "thumbs"))
    assert storyboard.generate_storyboard(8, str(source), 3.0)
    with Image.open(storyboard.sheet_path(8, 0)) as img:
        assert img.size == (320, 180)
    assert not storyboard.is_stale(8, str(source))


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg absent")
def test_a_long_video_is_split_into_full_sheets(tmp_path, monkeypatch):
    from PIL import Image

    source = tmp_path / "long.mp4"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=320x180:rate=5",
                    "-t", "1100", "-g", "50", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(source)], check=True)
    monkeypatch.setattr(storyboard.settings, "thumbnails_dir", str(tmp_path / "thumbs"))
    assert storyboard.generate_storyboard(9, str(source), 1100.0)
    with Image.open(storyboard.sheet_path(9, 0)) as first, Image.open(storyboard.sheet_path(9, 1)) as second:
        assert first.size == second.size == (10 * 320, 10 * 180)
    storyboard.remove_storyboard(9)
    assert not storyboard.storyboard_dir(9).exists()

