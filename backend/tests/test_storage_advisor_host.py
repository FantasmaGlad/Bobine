import os

os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_database.db"
os.environ["BOBINE_MEDIA_DIR"] = "data/test_videos"
os.environ["BOBINE_WATCH_DIR"] = "data/test_watched"
os.environ["BOBINE_THUMBNAILS_DIR"] = "data/test_thumbnails"

import pytest
from fastapi.testclient import TestClient

from app.api.routes import storage as storage_routes
from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_the_advice_defaults_to_the_host_bobine_runs_on(client, monkeypatch):
    monkeypatch.setattr(storage_routes, "os_key", lambda: "android")
    advice = client.get("/api/storage/advisor/format").json()
    assert advice["host_os"] == "android"
    assert advice["fstype"] in ("exfat", "vfat")


def test_an_explicit_host_still_wins(client, monkeypatch):
    monkeypatch.setattr(storage_routes, "os_key", lambda: "android")
    assert client.get("/api/storage/advisor/format?host=linux").json()["host_os"] == "linux"
