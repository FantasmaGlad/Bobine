import os

os.environ.setdefault("BOBINE_DATABASE_URL", "sqlite:///data/test_database.db")
os.environ.setdefault("BOBINE_MEDIA_DIR", "data/test_videos")
os.environ.setdefault("BOBINE_WATCH_DIR", "data/test_watched")
os.environ.setdefault("BOBINE_THUMBNAILS_DIR", "data/test_thumbnails")

import os
import subprocess
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from app.database import init_db
from app.main import app
from app.storage.service import StorageService
from storage_fakes import FakeStorageDriver
from storage_flow_support import HAS_FFMPEG, _cleanup_db


@pytest.fixture(scope="module")
def media(tmp_path_factory):
    folder = tmp_path_factory.mktemp("media")
    video, audio = folder / "Rpm 101 test.mp4", folder / "piste.mp3"
    if HAS_FFMPEG:
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=30", "-f", "lavfi", "-i", "sine=frequency=1000:duration=1",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(video)], capture_output=True, check=True)
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=800:duration=1", "-c:a", "libmp3lame", str(audio)], capture_output=True, check=True)
    return SimpleNamespace(video=video, audio=audio)


@pytest.fixture()
def env(tmp_path, monkeypatch):
    init_db()
    _cleanup_db()
    driver = FakeStorageDriver(tmp_path / "fake")
    service = StorageService(lambda: driver)
    monkeypatch.setattr("app.main.storage_service", service)
    monkeypatch.setattr("app.api.stream_response.storage_service", service)
    monkeypatch.setattr("app.api.routes.storage.service", service)
    with TestClient(app) as client:
        ns = SimpleNamespace(client=client, driver=driver, service=service, tmp=tmp_path)
        ns.refresh = lambda: client.portal.call(service.refresh)
        yield ns
    _cleanup_db()
