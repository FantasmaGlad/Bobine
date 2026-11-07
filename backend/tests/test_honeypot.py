"""Leurre d'intrusion (M16) : armé par le fichier de consigne, signalé une fois quand bom.txt apparaît, actif sur l'appliance seulement."""
import asyncio
import os

os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_database.db"
os.environ["BOBINE_MEDIA_DIR"] = "data/test_videos"
os.environ["BOBINE_WATCH_DIR"] = "data/test_watched"
os.environ["BOBINE_THUMBNAILS_DIR"] = "data/test_thumbnails"

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal, init_db
from app.main import app
from app.models import ActivityLog, Setting
from app.utils import honeypot


@pytest.fixture()
def trap(tmp_path, monkeypatch):
    monkeypatch.setenv("BOBINE_HONEYPOT_DIR", str(tmp_path / "leurre"))
    init_db()
    with SessionLocal() as db:
        db.query(ActivityLog).filter(ActivityLog.event_type == "intrusion_suspected").delete()
        db.query(Setting).filter(Setting.key == honeypot.REPORTED_KEY).delete()
        db.commit()
    return tmp_path / "leurre"


def arm(folder):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / honeypot.NOTICE_NAME).write_text("consigne", encoding="utf-8")


def reports():
    with SessionLocal() as db:
        return db.query(ActivityLog).filter(ActivityLog.event_type == "intrusion_suspected").count()


def test_nothing_is_watched_without_the_notice(trap):
    assert honeypot.status() == {"armed": False, "triggered": False}
    trap.mkdir()
    (trap / honeypot.TRIGGER_NAME).write_text("x", encoding="utf-8")  # bom.txt sans consigne : pas un leurre en place
    assert honeypot.is_triggered() is False and honeypot.report_once() is False and reports() == 0


def test_creating_bom_is_reported_once_even_after_a_restart(trap):
    arm(trap)
    assert honeypot.status() == {"armed": True, "triggered": False} and honeypot.report_once() is False
    (trap / honeypot.TRIGGER_NAME).write_text("controle-integrite-bobine\n", encoding="utf-8")
    assert honeypot.is_triggered() and honeypot.report_once() is True
    assert honeypot.report_once() is False and reports() == 1
    assert honeypot.report_once() is False  # même après un redémarrage : le marqueur est en base


def test_a_new_creation_is_reported_again(trap):
    arm(trap)
    bom = trap / honeypot.TRIGGER_NAME
    bom.write_text("a", encoding="utf-8")
    assert honeypot.report_once() is True
    bom.unlink()
    assert honeypot.report_once() is False
    bom.write_text("b", encoding="utf-8")
    assert honeypot.report_once() is True and reports() == 2


def test_diagnostic_flags_the_trigger_only_when_armed(trap):
    client = TestClient(app)
    assert not [p for p in client.get("/api/diagnostics/system").json()["problems"] if p["code"] == "honeypot_triggered"]
    unarmed = [c for c in client.get("/api/diagnostics/system").json()["checks"] if c["name"] == "honeypot"]
    assert all("leurre" not in c.get("detail", "") for c in unarmed)  # rien à signaler sans leurre déposé
    arm(trap)
    report = client.get("/api/diagnostics/system").json()
    assert any(c["name"] == "honeypot" and c.get("detail") == "leurre en place, intact" for c in report["checks"])
    (trap / honeypot.TRIGGER_NAME).write_text("x", encoding="utf-8")
    problems = [p for p in client.get("/api/diagnostics/system").json()["problems"] if p["code"] == "honeypot_triggered"]
    assert problems and problems[0]["severity"] == "critical"


def test_watching_starts_on_the_appliance_only(trap, monkeypatch):
    arm(trap)

    async def scenario(profile):
        monkeypatch.setattr("app.utils.deployment.get_deployment_profile", lambda: profile)
        started = honeypot.start()
        await honeypot.stop()
        return started

    assert asyncio.run(scenario("linux-headless")) is True
    assert asyncio.run(scenario("linux-desktop")) is False
    assert asyncio.run(scenario("windows")) is False


def test_the_notice_asks_for_no_secret():
    from pathlib import Path

    text = (Path(__file__).resolve().parents[2] / "packaging/appliance/leurre/LISEZ-MOI.txt").read_text(encoding="utf-8")
    assert honeypot.TRIGGER_NAME in text and "Aucun mot de passe" in text
    assert "mot de passe :" not in text.lower() and ".env" not in text
