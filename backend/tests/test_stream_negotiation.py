"""Négociation de la version servie par `GET /api/videos/{id}/stream` (lot F3
du plan Firefox) : l'original par défaut, la version web pour un client qui
annonce ne pas savoir décoder le codec, jamais une version web absente."""

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("BOBINE_DATABASE_URL", "sqlite:///data/test_database.db")
os.environ.setdefault("BOBINE_MEDIA_DIR", "data/test_videos")
os.environ.setdefault("BOBINE_WATCH_DIR", "data/test_watched")
os.environ.setdefault("BOBINE_THUMBNAILS_DIR", "data/test_thumbnails")

from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import ImportSource, Setting, Video  # noqa: E402

ORIGINAL = b"ORIGINAL-HEVC" * 50
WEB = b"WEB-H264" * 30


@pytest.fixture
def env(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'db.sqlite'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    counter = {"n": 0}

    def make(web_status, codec="hevc"):
        counter["n"] += 1
        n = counter["n"]  # file_path est unique en base : un jeu de fichiers par vidéo
        (tmp_path / f"orig{n}.mp4").write_bytes(ORIGINAL)
        (tmp_path / f"web{n}.mp4").write_bytes(WEB)
        with Session() as db:
            video = Video(
                file_path=str(tmp_path / f"orig{n}.mp4"), title="t", codec=codec, pix_fmt="yuv420p",
                width=1920, height=1080, fps=30.0, source=ImportSource.upload,
                web_path=str(tmp_path / f"web{n}.mp4") if web_status else None, web_status=web_status,
            )
            db.add(video)
            db.commit()
            return video.id

    def override():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = override
    yield TestClient(app), make, Session
    app.dependency_overrides.pop(get_db, None)


def test_no_negotiation_serves_original(env):
    client, make, _ = env
    vid = make("ready")
    r = client.get(f"/api/videos/{vid}/stream")
    assert r.content == ORIGINAL and r.headers["x-bobine-rendition"] == "original"


def test_client_without_hevc_gets_the_web_version(env):
    client, make, _ = env
    vid = make("ready")
    r = client.get(f"/api/videos/{vid}/stream?accept=h264")
    assert r.content == WEB and r.headers["x-bobine-rendition"] == "web"
    h = client.head(f"/api/videos/{vid}/stream?accept=h264")
    assert h.headers["x-bobine-rendition"] == "web" and h.headers["content-length"] == str(len(WEB))


def test_client_with_hevc_keeps_the_original(env):
    client, make, _ = env
    vid = make("ready")
    r = client.get(f"/api/videos/{vid}/stream?accept=h264,hevc")
    assert r.content == ORIGINAL and r.headers["x-bobine-rendition"] == "original"


def test_web_version_not_ready_falls_back_to_original(env):
    client, make, _ = env
    for status in (None, "pending", "error"):
        vid = make(status)
        r = client.get(f"/api/videos/{vid}/stream?accept=h264&profile=web")
        assert r.content == ORIGINAL, status


def test_forced_profile_original_beats_negotiation(env):
    client, make, _ = env
    vid = make("ready")
    r = client.get(f"/api/videos/{vid}/stream?accept=h264&profile=original")
    assert r.content == ORIGINAL


def test_h264_video_is_never_replaced_even_if_a_web_file_exists(env):
    client, make, _ = env
    vid = make("ready", codec="h264")
    r = client.get(f"/api/videos/{vid}/stream?accept=h264")
    assert r.content == ORIGINAL


def test_range_requests_work_on_the_web_version(env):
    client, make, _ = env
    vid = make("ready")
    r = client.get(f"/api/videos/{vid}/stream?accept=h264", headers={"Range": "bytes=0-7"})
    assert r.status_code == 206 and r.content == WEB[:8]


def test_incapable_client_triggers_generation_only_when_auto_is_enabled(env, monkeypatch):
    client, make, Session = env
    calls = []
    monkeypatch.setattr("app.main.request_web_rendition", lambda video_id: calls.append(video_id))
    vid = make(None)
    client.get(f"/api/videos/{vid}/stream?accept=h264")
    assert calls == []
    with Session() as db:
        db.add(Setting(key="auto_web_rendition", value="true"))
        db.commit()
    client.get(f"/api/videos/{vid}/stream?accept=h264")
    assert calls == [vid]
    client.get(f"/api/videos/{vid}/stream?accept=h264,hevc")  # client capable : rien à produire
    assert calls == [vid]
