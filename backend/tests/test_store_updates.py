"""Build Google Play : la section Mises à jour passe par Google Play (jamais de téléchargement d'APK
par Bobine) ; le build libre garde le téléchargement des releases."""

import os

os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_database.db"
os.environ["BOBINE_MEDIA_DIR"] = "data/test_videos"
os.environ["BOBINE_WATCH_DIR"] = "data/test_watched"
os.environ["BOBINE_THUMBNAILS_DIR"] = "data/test_thumbnails"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.utils.deployment import ProfileHandler, UpdateUnsupported  # noqa: E402


class PlayHandler(ProfileHandler):
    profile = "android"

    def __init__(self):
        self.calls = []
        self.state = {"state": "available", "version_code": 51, "flexible_allowed": True}

    def is_store_managed(self):
        return True

    def store_update_status(self):
        return self.state

    def store_update_start(self):
        self.calls.append("start")
        return {"ok": True}

    def store_update_complete(self):
        self.calls.append("complete")
        raise UpdateUnsupported("Rien à installer.")

    def store_open_listing(self):
        self.calls.append("open")
        return {"ok": True}


class FreeHandler(ProfileHandler):
    profile = "android"

    def is_store_managed(self):
        return False


@pytest.fixture()
def play(monkeypatch):
    init_db()
    handler = PlayHandler()
    monkeypatch.setattr("app.routers.updates.get_profile_handler", lambda: handler)
    monkeypatch.setattr("app.routers.settings.get_profile_handler", lambda: handler)
    return handler


def test_check_reports_store_state_and_never_offers_an_apk(play):
    body = TestClient(app).get("/api/updates/check").json()
    assert body["store_managed"] is True
    assert body["store"] == {"provider": "google_play", "state": "available", "version_code": 51, "flexible_allowed": True}
    assert body["can_auto_apply"] is False and body["download_url"] is None


def test_check_survives_an_unreachable_store(play, monkeypatch):
    def boom():
        raise RuntimeError("Play indisponible")

    monkeypatch.setattr(play, "store_update_status", boom)
    assert TestClient(app).get("/api/updates/check").json()["store"]["state"] == "unavailable"


def test_store_actions_are_triggered_and_errors_are_409(play):
    client = TestClient(app)
    assert client.post("/api/updates/store/start").json()["ok"] is True
    assert client.post("/api/updates/store/open").json()["ok"] is True
    refused = client.post("/api/updates/store/complete")
    assert refused.status_code == 409 and "Rien à installer" in refused.json()["detail"]
    assert play.calls == ["start", "open", "complete"]


def test_github_apply_is_refused_on_the_store_build(play):
    assert TestClient(app).post("/api/updates/apply").status_code == 400


def test_free_build_has_no_store_actions(monkeypatch):
    init_db()
    monkeypatch.setattr("app.routers.updates.get_profile_handler", lambda: FreeHandler())
    client = TestClient(app)
    for action in ("start", "complete", "open"):
        assert client.post(f"/api/updates/store/{action}").status_code == 400


def test_settings_expose_store_managed(play):
    assert TestClient(app).get("/api/settings").json()["store_managed"] is True
