"""ffmpeg/ffprobe : message clair quand le binaire est introuvable, `-nostdin` (ffmpeg),
`stdin=DEVNULL` et environnement assaini dans un build figé."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("BOBINE_DATABASE_URL", "sqlite:///data/test_database.db")
os.environ.setdefault("BOBINE_MEDIA_DIR", "data/test_videos")
os.environ.setdefault("BOBINE_WATCH_DIR", "data/test_watched")
os.environ.setdefault("BOBINE_THUMBNAILS_DIR", "data/test_thumbnails")

from app.utils import (  # noqa: E402
    audio_utils, chapters, ffmpeg_binaries, import_jobs, radio_utils, staged_uploads as staged, video_utils,
)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(staged, "staging_dir", lambda: tmp_path)
    from app.main import app

    return TestClient(app)


# ---------------------------------------------------------------------------
# ffmpeg / ffprobe introuvable
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("os_name,fragment", [
    ("macos", "brew install ffmpeg"), ("windows", "Réinstallez Bobine"),
    ("linux", "apt install ffmpeg"), ("android", "réinstallez Bobine"),
])
def test_missing_tool_message_explains_how_to_install(monkeypatch, os_name, fragment):
    monkeypatch.setattr(ffmpeg_binaries, "os_key", lambda: os_name)
    err = ffmpeg_binaries.MediaToolMissingError("ffmpeg", "FileNotFoundError: [Errno 2] No such file or directory: 'ffmpeg'")
    assert str(err).startswith("ffmpeg est introuvable")
    assert fragment in str(err)
    assert isinstance(err, ValueError)


def test_ffprobe_missing_raises_clear_error(monkeypatch):
    monkeypatch.setattr(video_utils, "FFPROBE_BIN", "/nonexistent/ffprobe")
    with pytest.raises(ffmpeg_binaries.MediaToolMissingError) as exc:
        video_utils.get_video_info("/tmp/x.mov")
    assert str(exc.value).startswith("ffprobe est introuvable")


def test_ffmpeg_missing_on_normalize_raises_clear_error(monkeypatch, tmp_path):
    monkeypatch.setattr(video_utils.subprocess, "Popen", _raising_popen(FileNotFoundError(2, "No such file or directory", "ffmpeg")))
    with pytest.raises(ffmpeg_binaries.MediaToolMissingError) as exc:
        video_utils._run_ffmpeg_with_progress([ffmpeg_binaries.FFMPEG_BIN, "-i", "a", "b"], None, 1.0)
    assert str(exc.value).startswith("ffmpeg est introuvable")
    assert "[Errno 2]" not in str(exc.value).split("(")[0]  # le détail technique est en fin de message seulement


def test_ffmpeg_missing_stops_thumbnail_retries_immediately(monkeypatch, tmp_path):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        raise FileNotFoundError(2, "No such file or directory", "ffmpeg")

    monkeypatch.setattr(video_utils.subprocess, "run", fake_run)
    monkeypatch.setattr(video_utils.time, "sleep", lambda s: pytest.fail("aucune pause attendue"))
    with pytest.raises(ffmpeg_binaries.MediaToolMissingError):
        video_utils.generate_thumbnail("/tmp/x.mp4", str(tmp_path), 10.0)
    assert len(calls) == 1


def test_missing_tool_error_is_classified_for_the_client():
    err = ffmpeg_binaries.MediaToolMissingError("ffprobe")
    code, params = ffmpeg_binaries.classify_error(str(err))
    assert code == "media_tool_missing" and params["tool"] == "ffprobe" and params["os"] in ("macos", "windows", "linux", "android")
    assert ffmpeg_binaries.classify_error("Le fichier est protégé par DRM") is None
    assert ffmpeg_binaries.classify_error(None) is None


def test_job_error_carries_code_and_params(client):
    job_id = import_jobs.create_job("video", "x.mov")
    import_jobs.update_job(job_id, stage="error", error=str(ffmpeg_binaries.MediaToolMissingError("ffmpeg")))
    body = next(j for j in client.get("/api/import-jobs").json() if j["id"] == job_id)
    assert body["error_code"] == "media_tool_missing"
    assert body["error_params"]["tool"] == "ffmpeg"
    other = import_jobs.create_job("video", "y.mov")
    import_jobs.update_job(other, stage="error", error="Fichier corrompu")
    body = next(j for j in client.get("/api/import-jobs").json() if j["id"] == other)
    assert body["error_code"] is None and body["error"] == "Fichier corrompu"


# ---------------------------------------------------------------------------
# -nostdin, stdin=DEVNULL, environnement
# ---------------------------------------------------------------------------

def _raising_popen(error):
    def popen(*args, **kwargs):
        raise error
    return popen


class _Recorder:
    def __init__(self):
        self.calls = []

    def run(self, cmd, **kwargs):
        self.calls.append((cmd, kwargs))
        out = '{"format": {"duration": "1.0"}, "streams": [], "chapters": []}'
        return subprocess.CompletedProcess(cmd, 0, out, "")


def test_ffprobe_calls_get_devnull_stdin_but_no_nostdin(monkeypatch, tmp_path):
    # ffprobe 8 refuse -nostdin (« Option not found ») : seul stdin=DEVNULL s'applique.
    rec = _Recorder()
    monkeypatch.setattr(subprocess, "run", rec.run)
    video_utils.get_video_info("/tmp/x.mp4")
    audio_utils.extract_audio_duration("/tmp/x.mp3")
    radio_utils.extract_radio_metadata("/tmp/x.mp3")
    chapters.read_embedded("/tmp/x.mkv")
    assert len(rec.calls) == 4
    for cmd, kwargs in rec.calls:
        assert kwargs["stdin"] == subprocess.DEVNULL, cmd
        assert "-nostdin" not in cmd, cmd


def test_ffmpeg_calls_get_nostdin_and_devnull_stdin(monkeypatch, tmp_path):
    rec = _Recorder()
    monkeypatch.setattr(subprocess, "run", rec.run)

    def fake_run_thumb(cmd, **kwargs):
        rec.calls.append((cmd, kwargs))
        Path(cmd[-1]).write_bytes(b"\xff\xd8jpeg")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(video_utils.subprocess, "run", fake_run_thumb)
    video_utils.generate_thumbnail("/tmp/x.mp4", str(tmp_path), 10.0)
    monkeypatch.setattr(subprocess, "run", rec.run)
    radio_utils.transcode_to_web("/tmp/a.wma", str(tmp_path / "a.m4a"))
    radio_utils._measure_loudnorm("/tmp/a.mp3", -16.0)
    for cmd, kwargs in rec.calls:
        if cmd[0] != ffmpeg_binaries.FFMPEG_BIN:
            continue
        assert cmd[1] == "-nostdin", cmd
        assert kwargs["stdin"] == subprocess.DEVNULL, cmd
    assert any(c[0][0] == ffmpeg_binaries.FFMPEG_BIN for c in rec.calls)


def test_normalize_popen_gets_nostdin_devnull_and_keeps_progress(monkeypatch):
    seen = {}

    class FakeProc:
        stdout = None
        stderr = None
        returncode = 0
        pid = 0

        def wait(self, timeout=None):
            return 0

    def fake_popen(cmd, **kwargs):
        seen["cmd"], seen["kwargs"] = cmd, kwargs
        return FakeProc()

    monkeypatch.setattr(video_utils.subprocess, "Popen", fake_popen)
    ret, _ = video_utils._run_ffmpeg_with_progress([ffmpeg_binaries.FFMPEG_BIN, "-i", "a", "b.mp4"], None, None)
    assert ret == 0
    assert seen["cmd"][:2] == [ffmpeg_binaries.FFMPEG_BIN, "-nostdin"]
    assert "-progress" in seen["cmd"]
    assert seen["kwargs"]["stdin"] == subprocess.DEVNULL


def test_with_nostdin_is_idempotent():
    cmd = ["ffmpeg", "-i", "a"]
    once = ffmpeg_binaries.with_nostdin(cmd)
    assert once == ["ffmpeg", "-nostdin", "-i", "a"]
    assert ffmpeg_binaries.with_nostdin(once) == once
    assert cmd == ["ffmpeg", "-i", "a"]


def test_frozen_build_gets_clean_library_env(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("LD_LIBRARY_PATH", "/bundle/lib")
    monkeypatch.setenv("LD_LIBRARY_PATH_ORIG", "/host/lib")
    monkeypatch.setenv("DYLD_LIBRARY_PATH", "/bundle/dylib")
    monkeypatch.delenv("DYLD_LIBRARY_PATH_ORIG", raising=False)
    kwargs = ffmpeg_binaries.media_subprocess_kwargs()
    assert kwargs["stdin"] == subprocess.DEVNULL
    assert kwargs["env"]["LD_LIBRARY_PATH"] == "/host/lib"
    assert "DYLD_LIBRARY_PATH" not in kwargs["env"]
    assert "LD_LIBRARY_PATH_ORIG" not in kwargs["env"]


def test_non_frozen_build_inherits_environment(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert "env" not in ffmpeg_binaries.media_subprocess_kwargs()


def test_clean_subprocess_env_also_restores_macos_library_path(monkeypatch):
    from app.utils import update_orchestrator as orch

    monkeypatch.setenv("DYLD_LIBRARY_PATH", "/bundle/dylib")
    monkeypatch.setenv("DYLD_LIBRARY_PATH_ORIG", "/host/dylib")
    monkeypatch.setenv("LIBPATH", "/bundle/aix")
    monkeypatch.delenv("LIBPATH_ORIG", raising=False)
    env = orch.clean_subprocess_env()
    assert env["DYLD_LIBRARY_PATH"] == "/host/dylib"
    assert "DYLD_LIBRARY_PATH_ORIG" not in env
    assert "LIBPATH" not in env
