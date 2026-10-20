"""GET /api/diagnostics/import : chaque bloc est défensif, jamais de HTTP 500."""

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("BOBINE_DATABASE_URL", "sqlite:///data/test_database.db")
os.environ.setdefault("BOBINE_MEDIA_DIR", "data/test_videos")
os.environ.setdefault("BOBINE_WATCH_DIR", "data/test_watched")
os.environ.setdefault("BOBINE_THUMBNAILS_DIR", "data/test_thumbnails")

from app.utils import ffmpeg_binaries, import_jobs, staged_uploads as staged  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(staged, "staging_dir", lambda: tmp_path)
    from app.main import app

    return TestClient(app)


# ---------------------------------------------------------------------------
# GET /api/diagnostics/import
# ---------------------------------------------------------------------------

def test_diagnostics_reports_every_block(client):
    r = client.get("/api/diagnostics/import")
    assert r.status_code == 200
    body = r.json()
    for key in ("os", "frozen", "ffmpeg", "ffprobe", "temp_dir", "staging_dir", "media_dir", "executors", "jobs", "problems"):
        assert key in body, key
    assert body["temp_dir"]["writable"] is True
    assert body["temp_dir"]["free_bytes"] > 0
    assert body["executors"]["ffmpeg"]["max_workers"] == 1
    assert isinstance(body["problems"], list)


def test_diagnostics_flags_missing_ffmpeg(client, monkeypatch):
    monkeypatch.setattr(ffmpeg_binaries, "FFMPEG_BIN", "/nonexistent/ffmpeg")
    monkeypatch.setattr(ffmpeg_binaries, "FFPROBE_BIN", "/nonexistent/ffprobe")
    body = client.get("/api/diagnostics/import").json()
    assert body["ffmpeg"]["found"] is False and body["ffmpeg"]["error"] == "introuvable"
    assert {"ffmpeg_unavailable", "ffprobe_unavailable"} <= set(body["problems"])


def test_diagnostics_shows_active_jobs_with_age_and_flags_stuck_one(client):
    job_id = import_jobs.create_job("video", "x.mov")
    import_jobs.update_job(job_id, stage="normalizing")
    with import_jobs._lock:
        import_jobs._jobs[job_id]["created_at"] -= 900
        import_jobs._jobs[job_id]["updated_at"] -= 600
    body = client.get("/api/diagnostics/import").json()
    mine = next(j for j in body["jobs"]["active"] if j["id"] == job_id[:8])
    assert mine["stage"] == "normalizing" and mine["age_seconds"] >= 900 and mine["idle_seconds"] >= 600
    assert "job_stuck" in body["problems"]


def test_diagnostics_never_returns_500_when_a_block_fails(client, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("panne simulée")

    monkeypatch.setattr(ffmpeg_binaries, "probe_tool", boom)
    monkeypatch.setattr(import_jobs, "list_jobs", boom)
    monkeypatch.setattr(staged, "staging_dir", boom)
    r = client.get("/api/diagnostics/import")
    assert r.status_code == 200
    body = r.json()
    assert "panne simulée" in body["ffmpeg"]["error"]
    assert "panne simulée" in body["jobs"]["error"]
    assert "panne simulée" in body["staging_dir"]["error"]
    assert body["temp_dir"]["writable"] is True  # les autres blocs restent exploitables


def test_diagnostics_detects_unwritable_temp_dir(client, monkeypatch, tmp_path):
    missing = tmp_path / "absent"
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(missing))
    body = client.get("/api/diagnostics/import").json()
    assert body["temp_dir"]["exists"] is False
    assert "temp_not_writable" in body["problems"]
