"""Corrections que `bobine diagnose --auto-fix` peut appliquer : décrites par le diagnostic, jamais devinées par la commande."""
import os

os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_database.db"
os.environ["BOBINE_MEDIA_DIR"] = "data/test_videos"
os.environ["BOBINE_WATCH_DIR"] = "data/test_watched"
os.environ["BOBINE_THUMBNAILS_DIR"] = "data/test_thumbnails"

from app.routers import diagnostics


def test_problem_carries_its_fix_only_when_given():
    report = diagnostics._Report()
    report.problem("a", "sans_fix", "info", "m", "r")
    report.problem("b", "avec_fix", "info", "m", "r", fix={"action": "set_settings", "settings": {"media_native": "false"}})
    assert "fix" not in report.problems[0] and report.problems[1]["fix"]["action"] == "set_settings"


def test_stuck_imports_expose_their_full_job_ids(monkeypatch):
    monkeypatch.setattr(diagnostics, "_jobs_state", lambda: {"active": [
        {"id": "abcdef01", "job_id": "abcdef0123456789", "idle_seconds": 9999}], "counts": {}})
    monkeypatch.setattr(diagnostics, "_executor_state", lambda: {"ffmpeg": {"shutdown": False}})
    monkeypatch.setattr(diagnostics, "_staging_state", lambda: {})
    report = diagnostics._Report()
    diagnostics._probe_imports(report)
    assert report.problems[0]["fix"] == {"action": "cancel_import_jobs", "job_ids": ["abcdef0123456789"]}
