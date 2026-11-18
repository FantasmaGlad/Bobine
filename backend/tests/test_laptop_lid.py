import os

os.environ.setdefault("BOBINE_DATABASE_URL", "sqlite:///data/test_database.db")
os.environ.setdefault("BOBINE_MEDIA_DIR", "data/test_videos")
os.environ.setdefault("BOBINE_WATCH_DIR", "data/test_watched")
os.environ.setdefault("BOBINE_THUMBNAILS_DIR", "data/test_thumbnails")

from types import SimpleNamespace  # noqa: E402

from starlette.testclient import TestClient  # noqa: E402

from app.api.routes.settings import laptop_lid  # noqa: E402
from app.main import app  # noqa: E402


def test_macbook_lid_setting_is_not_offered(monkeypatch):
    monkeypatch.setattr(laptop_lid.sys, "platform", "darwin")
    monkeypatch.setattr(laptop_lid.psutil, "sensors_battery", lambda: SimpleNamespace(percent=80))
    client = TestClient(app)
    assert client.get("/api/settings/laptop-lid").json() == {"has_lid": False, "prevent_sleep": False}
    assert client.post("/api/settings/laptop-lid", json={"prevent_sleep": True}).status_code == 409
