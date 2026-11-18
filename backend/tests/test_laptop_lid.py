import os

os.environ.setdefault("BOBINE_DATABASE_URL", "sqlite:///data/test_database.db")
os.environ.setdefault("BOBINE_MEDIA_DIR", "data/test_videos")
os.environ.setdefault("BOBINE_WATCH_DIR", "data/test_watched")
os.environ.setdefault("BOBINE_THUMBNAILS_DIR", "data/test_thumbnails")

import sys  # noqa: E402
from types import SimpleNamespace  # noqa: E402

import psutil  # noqa: E402

from starlette.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def test_macbook_lid_setting_is_not_offered(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(psutil, "sensors_battery", lambda: SimpleNamespace(percent=80))
    client = TestClient(app)
    assert client.get("/api/settings/laptop-lid").json() == {"has_lid": False, "prevent_sleep": False}
    assert client.post("/api/settings/laptop-lid", json={"prevent_sleep": True}).status_code == 409
