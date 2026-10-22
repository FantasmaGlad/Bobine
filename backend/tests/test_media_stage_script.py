"""Smoke check used before the audio component is staged into a package."""
import importlib.util
from pathlib import Path
import stat
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
BINARY = ROOT / "media" / "target" / "release" / ("bobine-media.exe" if sys.platform == "win32" else "bobine-media")


@pytest.fixture(scope="module")
def stage():
    spec = importlib.util.spec_from_file_location("stage_media", ROOT / "scripts" / "ci" / "stage-media.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.skipif(not BINARY.is_file(), reason="native release binary has not been built")
def test_real_binary_answers_hello_and_exits_on_eof(stage):
    result = stage.smoke(BINARY)
    assert result["protocol_version"] == 1 and result["formats"] == ["mp3", "flac", "wav", "m4a", "ogg", "opus", "aiff", "aif"]


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX shell stand-ins")
def test_smoke_rejects_silent_wrong_and_unclean_executables(stage, tmp_path):
    def script(name, body):
        path = tmp_path / name
        path.write_text("#!/bin/sh\n" + body)
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
        return path

    silent = script("silent", "sleep 5\n")
    with pytest.raises(RuntimeError, match="no answer"):
        stage.smoke(silent, timeout=0.3)
    wrong = script("wrong", 'read line; echo \'{"jsonrpc":"2.0","id":1,"result":{"protocol_version":2}}\'\n')
    with pytest.raises(RuntimeError, match="unexpected hello"):
        stage.smoke(wrong)
    unclean = script("unclean", 'read line; echo \'{"jsonrpc":"2.0","id":1,"result":{"protocol_version":1}}\'; cat >/dev/null; exit 3\n')
    with pytest.raises(RuntimeError, match="exit status 3"):
        stage.smoke(unclean)


@pytest.mark.skipif(not BINARY.is_file(), reason="native release binary has not been built")
def test_script_check_mode_reports_an_installed_executable(tmp_path):
    import json
    import subprocess

    script = ROOT / "scripts" / "ci" / "stage-media.py"
    done = subprocess.run([sys.executable, str(script), "--check", str(BINARY)], capture_output=True, text=True, timeout=30)
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout)["protocol_version"] == 1
    # Without --check, a destination directory is required.
    missing = subprocess.run([sys.executable, str(script), "--dest", str(tmp_path / "absent")], capture_output=True, text=True, timeout=30)
    assert missing.returncode != 0
