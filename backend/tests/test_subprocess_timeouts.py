import os

os.environ.setdefault("BOBINE_DATABASE_URL", "sqlite:///data/test_database.db")
os.environ.setdefault("BOBINE_MEDIA_DIR", "data/test_videos")
os.environ.setdefault("BOBINE_WATCH_DIR", "data/test_watched")
os.environ.setdefault("BOBINE_THUMBNAILS_DIR", "data/test_thumbnails")

import subprocess  # noqa: E402

import pytest  # noqa: E402

from app.api.routes.settings import laptop_lid  # noqa: E402
from app.utils import audio_utils, radio_utils  # noqa: E402


@pytest.fixture
def hanging_tool(monkeypatch):
    calls: list[dict] = []

    def run(cmd, **kwargs):
        calls.append(kwargs.get("timeout"))
        raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout") or 0)

    monkeypatch.setattr(subprocess, "run", run)
    yield calls
    assert calls and all(calls), f"every command needs a timeout: {calls}"


def test_probes_give_up_on_a_hanging_tool(hanging_tool, tmp_path):
    assert audio_utils.extract_audio_duration("a.mp3") is None
    assert radio_utils.extract_radio_metadata("a.mp3")["duration_seconds"] is None
    assert radio_utils.extract_embedded_cover("a.mp3", str(tmp_path), "1") is None
    assert radio_utils._measure_loudnorm("a.mp3", -10.0) is None
    assert len(hanging_tool) == 4


def test_long_audio_jobs_fail_on_a_hanging_tool(hanging_tool, tmp_path):
    with pytest.raises(subprocess.TimeoutExpired):
        radio_utils.transcode_to_web("a.flac", str(tmp_path / "a.m4a"))
    with pytest.raises(subprocess.TimeoutExpired):
        radio_utils.normalize_announcement_loudness("a.mp3", str(tmp_path / "b.m4a"))


@pytest.mark.parametrize("platform", ["win32", "linux"])
def test_laptop_lid_commands_are_bounded(hanging_tool, monkeypatch, platform):
    monkeypatch.setattr(laptop_lid.sys, "platform", platform)
    monkeypatch.setattr(laptop_lid.shutil, "which", lambda name: f"/usr/bin/{name}")
    assert laptop_lid._get_lid_prevent_sleep() is False
    assert laptop_lid._set_lid_prevent_sleep(True) is False
    assert hanging_tool
