"""Un export statique par langue : celui de la langue enregistrée est servi, le changement demande un redémarrage."""
import os

os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_database.db"
os.environ["BOBINE_MEDIA_DIR"] = "data/test_videos"
os.environ["BOBINE_WATCH_DIR"] = "data/test_watched"
os.environ["BOBINE_THUMBNAILS_DIR"] = "data/test_thumbnails"

import pytest
from fastapi.testclient import TestClient
from starlette.staticfiles import StaticFiles

from app.main import app
from app.utils import ui_language
from app.utils.deployment import get_profile_handler


def _export(root, language=None, text="x"):
    folder = root / language if language else root
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "index.html").write_text(f"<html lang='{language or 'fr'}'>{text}</html>", encoding="utf-8")


def test_each_language_is_served_from_its_own_export(tmp_path):
    _export(tmp_path, "fr", "bonjour")
    _export(tmp_path, "en", "hello")
    site = TestClient(ui_language.LanguageFrontend(tmp_path, StaticFiles))
    try:
        ui_language.set_served("fr")
        assert "bonjour" in site.get("/").text
        ui_language.set_served("en")
        assert "hello" in site.get("/").text
        ui_language.set_served("de")
        assert ui_language.served() == "fr" and "bonjour" in site.get("/").text
    finally:
        ui_language.set_served("fr")


def test_single_export_of_an_older_build_is_still_served(tmp_path):
    _export(tmp_path, None, "ancien")
    assert ui_language.build_dir(tmp_path, "en") == tmp_path
    ui_language.set_served("en")
    try:
        assert "ancien" in TestClient(ui_language.LanguageFrontend(tmp_path, StaticFiles)).get("/").text
    finally:
        ui_language.set_served("fr")


@pytest.fixture()
def client():
    from app.database import SessionLocal
    from app.models import Setting

    def clean():
        with SessionLocal() as db:
            db.query(Setting).filter(Setting.key.in_(("language", "simplified_ui"))).delete(synchronize_session=False)
            db.commit()

    with TestClient(app) as test_client:
        clean()
        ui_language.set_served("fr")
        yield test_client
        clean()
        ui_language.set_served("fr")


def test_language_change_requires_a_restart(client):
    settings = client.get("/api/settings").json()
    assert settings["language"] == "fr" and settings["ui_language"] == "fr" and settings["language_restart_required"] is False
    client.put("/api/settings", json={"language": "en"})
    settings = client.get("/api/settings").json()
    assert settings["language"] == "en" and settings["ui_language"] == "fr" and settings["language_restart_required"] is True


def test_startup_serves_the_stored_language(client):
    from app.database import SessionLocal
    from app.api.routes import settings as settings_router

    client.put("/api/settings", json={"language": "en"})
    with SessionLocal() as db:
        assert settings_router.stored_language(db) == "en"
    client.put("/api/settings", json={"language": "fr"})
    with SessionLocal() as db:
        assert settings_router.stored_language(db) == "fr"


def test_simplified_ui_setting_roundtrip_and_validation(client):
    assert client.get("/api/settings").json()["simplified_ui"] == "false"
    assert client.put("/api/settings", json={"simplified_ui": "true"}).status_code == 200
    assert client.get("/api/settings").json()["simplified_ui"] == "true"
    assert client.put("/api/settings", json={"simplified_ui": "peut-etre"}).status_code == 400


def test_restart_endpoint_restarts_the_service(client, monkeypatch):
    calls = []
    monkeypatch.setattr(get_profile_handler().__class__, "restart_services", lambda self: calls.append("restart"))
    async def no_wait(_seconds):
        return None
    monkeypatch.setattr("app.api.routes.settings.maintenance.asyncio.sleep", no_wait)
    response = client.post("/api/settings/system/restart")
    assert response.status_code == 200 and response.json()["status"] == "restarting"
    assert calls == ["restart"]


def test_lifespan_serves_the_stored_language():
    from app.database import SessionLocal
    from app.models import Setting

    def stored(value):
        with SessionLocal() as db:
            db.query(Setting).filter(Setting.key == "language").delete(synchronize_session=False)
            if value:
                db.add(Setting(key="language", value=value))
            db.commit()

    try:
        for language in ("en", "fr"):
            stored(language)
            with TestClient(app):
                assert ui_language.served() == language
    finally:
        stored(None)
        ui_language.set_served("fr")


def test_partial_build_falls_back_to_the_other_language(tmp_path):
    _export(tmp_path, "fr", "bonjour")
    assert ui_language.build_dir(tmp_path, "en") == tmp_path / "fr"


def test_restart_endpoint_is_logged(client, monkeypatch):
    monkeypatch.setattr(get_profile_handler().__class__, "restart_services", lambda self: None)
    client.post("/api/settings/system/restart")
    assert any("Redémarrage demandé" in entry.get("message", "") for entry in client.get("/api/logs", params={"source": "activity"}).json().get("entries", []))


def test_restart_reports_whether_a_relaunch_is_guaranteed(client, monkeypatch):
    from app.utils.deployment_profiles.android import AndroidHandler
    from app.utils.deployment_profiles.linux_desktop import LinuxDesktopHandler

    assert LinuxDesktopHandler().restart_is_guaranteed() is True
    assert AndroidHandler().restart_is_guaranteed() is False
    monkeypatch.setattr(get_profile_handler().__class__, "restart_services", lambda self: None)
    monkeypatch.setattr(get_profile_handler().__class__, "restart_is_guaranteed", lambda self: False)
    assert client.post("/api/settings/system/restart").json()["restart_guaranteed"] is False
    assert client.get("/api/settings").json()["restart_guaranteed"] is False


def test_shared_assets_are_served_for_both_languages(tmp_path):
    _export(tmp_path, "fr", "bonjour")
    _export(tmp_path, "en", "hello")
    (tmp_path / "_shared" / "_next").mkdir(parents=True)
    (tmp_path / "_shared" / "_next" / "app.js").write_text("commun", encoding="utf-8")
    (tmp_path / "en" / "only.txt").write_text("anglais", encoding="utf-8")
    site = TestClient(ui_language.LanguageFrontend(tmp_path, StaticFiles))
    try:
        for language in ("fr", "en"):
            ui_language.set_served(language)
            assert site.get("/_next/app.js").text == "commun"
        ui_language.set_served("fr")
        from starlette.exceptions import HTTPException

        with pytest.raises(HTTPException) as missing:
            site.get("/only.txt")
        assert missing.value.status_code == 404
        assert site.get("/").status_code == 200
    finally:
        ui_language.set_served("fr")
