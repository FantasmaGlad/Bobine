"""Diagnostic système et journaux unifiés : constats typés à code stable triés par gravité, sonde en échec rendue
`unknown` sans erreur 500 ; journaux en JSON stable (UTC, niveau minimal, `since` avec fuseau, archives, traces
rattachées à leur entrée)."""

import os
import time
from datetime import datetime

os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_database.db"
os.environ["BOBINE_MEDIA_DIR"] = "data/test_videos"
os.environ["BOBINE_WATCH_DIR"] = "data/test_watched"
os.environ["BOBINE_THUMBNAILS_DIR"] = "data/test_thumbnails"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.api.routes import diagnostics  # noqa: E402


@pytest.fixture()
def client():
    init_db()
    return TestClient(app)


def test_healthy_report_lists_every_check(client):
    report = client.get("/api/diagnostics/system").json()
    assert report["schema"] == 1 and report["generated_at"].endswith("Z")
    names = [check["name"] for check in report["checks"]]
    for expected in ("database", "kiosk", "port", "network", "media_tools", "disk", "imports", "updates", "storage"):
        assert expected in names
    assert all(set(p) - {"fix"} == {"code", "severity", "message", "remedy"} for p in report["problems"])


def test_problems_are_typed_and_sorted_by_severity(client, monkeypatch):
    monkeypatch.setattr(diagnostics.ffmpeg_binaries, "probe_tool", lambda binary: {"found": False})
    monkeypatch.setattr("app.utils.port.active_port", lambda: 1904)
    monkeypatch.setattr("app.utils.port.read_runtime", lambda **kwargs: {"preferred": 1903})
    report = client.get("/api/diagnostics/system").json()
    assert report["status"] == "critical"
    codes = [p["code"] for p in report["problems"]]
    assert {"ffmpeg_unavailable", "ffprobe_unavailable", "port_fallback"} <= set(codes)
    assert [p["severity"] for p in report["problems"]] == sorted(
        (p["severity"] for p in report["problems"]), key=diagnostics.SEVERITIES.index,
    )
    port = next(p for p in report["problems"] if p["code"] == "port_fallback")
    assert "1904" in port["message"] and "1903" in port["remedy"]


def test_a_failing_probe_is_unknown_not_an_error(client, monkeypatch):
    def broken():
        raise RuntimeError("liste des interfaces illisible")

    monkeypatch.setattr("app.utils.network.lan_addresses", broken)
    answer = client.get("/api/diagnostics/system")
    assert answer.status_code == 200
    network = next(c for c in answer.json()["checks"] if c["name"] == "network")
    assert network["status"] == "unknown" and "illisible" in network["detail"]
    if not answer.json()["problems"]:
        assert answer.json()["status"] == "unknown"


# --- journaux ---------------------------------------------------------------------------------------------------------

@pytest.fixture()
def technical_log(tmp_path, monkeypatch):
    if not hasattr(time, "tzset"):
        pytest.skip("heure locale non pilotable par TZ sur cette plateforme")
    previous = os.environ.get("TZ")
    os.environ["TZ"] = "Europe/Paris"
    time.tzset()
    log = tmp_path / "technical.log"
    (tmp_path / "technical.log.1").write_text(
        "2026-11-04 23:00:00,000 INFO app.ancien: entrée archivée\n", encoding="utf-8",
    )
    log.write_text(
        "ligne orpheline d'un fichier tourné\n"
        "2026-11-05 10:00:00,250 INFO app.main: démarrage\n"
        "2026-11-05 10:05:00,000 ERROR app.api.routes.settings: échec de diffusion\n"
        "Traceback (most recent call last):\n"
        "  ValueError: exemple\n"
        "2026-11-05 10:06:00,000 WARNING app.utils.mdns: ré-annonce en échec\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("app.api.routes.logs.settings", type("S", (), {"technical_log_path": log})())
    yield
    if previous is None:
        os.environ.pop("TZ", None)
    else:
        os.environ["TZ"] = previous
    time.tzset()


def test_technical_log_is_parsed_newest_first_in_utc(client, technical_log):
    answer = client.get("/api/logs?limit=10").json()
    assert answer["schema"] == 1 and answer["source"] == "technical"
    assert [e["timestamp"] for e in answer["entries"]] == [
        "2026-11-05T09:06:00.000Z", "2026-11-05T09:05:00.000Z", "2026-11-05T09:00:00.250Z", "2026-11-04T22:00:00.000Z",
    ]
    error = answer["entries"][1]
    assert error["level"] == "error" and error["category"] == "app.api.routes.settings"
    assert error["message"].endswith("Traceback (most recent call last):\n  ValueError: exemple")
    assert answer["skipped_unparsed"] == 1 and answer["truncated"] is False


def test_filters_level_since_and_limit(client, technical_log):
    assert [e["level"] for e in client.get("/api/logs?level=warning").json()["entries"]] == ["warning", "error"]
    recent = client.get("/api/logs", params={"since": "2026-11-05T09:01:00Z"}).json()
    assert [e["category"] for e in recent["entries"]] == ["app.utils.mdns", "app.api.routes.settings"]
    limited = client.get("/api/logs?limit=1").json()
    assert limited["count"] == 1 and limited["truncated"] is True


def test_invalid_parameters_are_refused(client):
    assert client.get("/api/logs?since=2026-11-05T09:00:00").json()["detail"]["code"] == "invalid_since"
    assert client.get("/api/logs?level=bavard").json()["detail"]["code"] == "invalid_level"
    assert client.get("/api/logs?source=ailleurs").json()["detail"]["code"] == "invalid_source"


def test_activity_log_shares_the_same_shape(client):
    from app.database import SessionLocal
    from app.utils.activity_log import log_activity

    with SessionLocal() as db:
        log_activity(db, "playlist_started", "Lundi soir")
    answer = client.get("/api/logs?source=activity&limit=1").json()
    entry = answer["entries"][0]
    assert set(entry) == {"timestamp", "level", "category", "message"} and entry["timestamp"].endswith("Z")
    assert client.get("/api/logs?source=activity&level=error").json()["entries"] == []
    assert datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00")).tzinfo is not None


def test_repeated_local_hour_keeps_utc_order(client, technical_log, tmp_path):
    """Le retour à l'heure d'hiver répète 02:00-03:00 : les deux passages doivent rester en UTC et dans l'ordre."""
    (tmp_path / "technical.log.1").unlink()
    (tmp_path / "technical.log").write_text(
        "2026-10-25 02:30:00,000 INFO app.main: premier passage\n"
        "2026-10-25 02:59:00,000 INFO app.main: fin du premier passage\n"
        "2026-10-25 02:00:00,000 INFO app.main: début du second passage\n"
        "2026-10-25 02:10:00,000 INFO app.main: second passage\n"
        "2026-10-25 02:30:00,000 INFO app.main: fin du second passage\n",
        encoding="utf-8",
    )
    answer = client.get("/api/logs?limit=10").json()
    assert [e["timestamp"] for e in answer["entries"]] == [
        "2026-10-25T01:30:00.000Z", "2026-10-25T01:10:00.000Z", "2026-10-25T01:00:00.000Z",
        "2026-10-25T00:59:00.000Z", "2026-10-25T00:30:00.000Z",
    ]
    recent = client.get("/api/logs", params={"since": "2026-10-25T01:05:00Z"}).json()
    assert [e["timestamp"] for e in recent["entries"]] == ["2026-10-25T01:30:00.000Z", "2026-10-25T01:10:00.000Z"]


def test_rotation_while_reading_neither_duplicates_nor_fails(client, technical_log, tmp_path, monkeypatch):
    from app.api.routes import logs

    original = logs._parse_technical
    rotated = []

    def rotate_then_parse(handle):
        if not rotated:  # le serveur fait tourner ses journaux juste après l'ouverture
            rotated.append(True)
            (tmp_path / "technical.log.1").replace(tmp_path / "technical.log.2")
            (tmp_path / "technical.log").replace(tmp_path / "technical.log.1")
        return original(handle)

    monkeypatch.setattr(logs, "_parse_technical", rotate_then_parse)
    answer = client.get("/api/logs?limit=50")
    assert answer.status_code == 200
    messages = [e["message"] for e in answer.json()["entries"]]
    assert len(messages) == len(set(messages)) == 4
