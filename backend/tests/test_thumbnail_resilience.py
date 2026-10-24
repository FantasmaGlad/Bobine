"""Miniatures : dépassement de délai ffmpeg, miniature de secours, service sans dossier (jamais de 500)."""

import os
import subprocess
from pathlib import Path

os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_database.db"
os.environ["BOBINE_MEDIA_DIR"] = "data/test_videos"
os.environ["BOBINE_WATCH_DIR"] = "data/test_watched"
os.environ["BOBINE_THUMBNAILS_DIR"] = "data/test_thumbnails"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from app.utils import video_utils  # noqa: E402


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(video_utils.time, "sleep", lambda s: None)


def _fake_run_factory(outcomes):
    """Chaque appel consomme un résultat : 'timeout', 'fail' ou 'ok' (écrit le fichier de sortie)."""
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        outcome = outcomes[min(len(calls) - 1, len(outcomes) - 1)]
        if outcome == "timeout":
            raise subprocess.TimeoutExpired(cmd, 30)
        if outcome == "fail":
            raise subprocess.CalledProcessError(1, cmd, stderr="Invalid data")
        Path(cmd[-1]).write_bytes(b"\xff\xd8jpeg")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    return fake_run, calls


def test_timeout_does_not_abort_the_fallbacks(tmp_path, monkeypatch):
    fake, calls = _fake_run_factory(["timeout", "timeout", "ok"])
    monkeypatch.setattr(video_utils.subprocess, "run", fake)
    path = video_utils.generate_thumbnail("video.mp4", str(tmp_path), 120.0)
    assert Path(path).stat().st_size > 0
    assert len(calls) == 3  # 10 %, 0,1 s puis 0 s : le dépassement du premier essai n'a pas tout interrompu


def test_transient_failures_get_a_last_retry(tmp_path, monkeypatch):
    fake, calls = _fake_run_factory(["fail", "fail", "fail", "ok"])
    monkeypatch.setattr(video_utils.subprocess, "run", fake)
    assert Path(video_utils.generate_thumbnail("video.mp4", str(tmp_path), 60.0)).exists()
    assert len(calls) == 4


def test_missing_binary_is_a_clean_error(tmp_path, monkeypatch):
    def boom(cmd, **kwargs):
        raise FileNotFoundError("ffmpeg")

    monkeypatch.setattr(video_utils.subprocess, "run", boom)
    with pytest.raises(ValueError):
        video_utils.generate_thumbnail("video.mp4", str(tmp_path), 60.0)


def test_placeholder_is_a_valid_jpeg_even_for_odd_titles(tmp_path):
    for title in ("Ambiance forêt", "", "---", "日本語"):
        out = video_utils.generate_placeholder_thumbnail(str(tmp_path / "sub"), title)
        with Image.open(out) as img:
            assert img.format == "JPEG" and img.size == (640, 360)


def test_thumbnail_route_without_directory_is_never_a_500():
    from app.main import app
    from app.config import settings
    import shutil

    directory = Path(settings.thumbnails_dir)
    shutil.rmtree(directory, ignore_errors=True)
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/thumbnails/thumb_absent.jpg")
    assert response.status_code == 404
    assert directory.is_dir()  # recréé au passage
