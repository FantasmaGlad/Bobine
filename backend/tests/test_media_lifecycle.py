"""Binary discovery in packaged layouts, parent death, and gapless duration parity.

The tests that need the native executable or ffmpeg skip when they are absent, like the
other optional-component tests; the Rust suite covers the same rules on every platform.
"""
from pathlib import Path
import os
import shutil
import signal
import subprocess
import sys
import textwrap
import time

import pytest

from app.utils import audio_utils
from app.utils import media_sidecar as media

REPO = Path(__file__).resolve().parents[2]
NATIVE = REPO / "media" / "target" / "release" / ("bobine-media.exe" if sys.platform == "win32" else "bobine-media")
needs_binary = pytest.mark.skipif(not NATIVE.is_file(), reason="native release binary has not been built")


def _executable(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"#!/bin/sh\n")
    path.chmod(0o755)
    return path


@pytest.fixture
def frozen(monkeypatch):
    monkeypatch.delenv("BOBINE_MEDIA_SIDECAR", raising=False)
    monkeypatch.delenv("BOBINE_MEDIA_BIN", raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)


@pytest.mark.skipif(os.name == "nt", reason="POSIX executable bits")
def test_frozen_linux_layout_finds_the_binary_next_to_the_executable(tmp_path, frozen, monkeypatch):
    monkeypatch.setattr(sys, "executable", str(tmp_path / "Bobine" / "BobineBackend"))
    assert media.find_binary() is None
    binary = _executable(tmp_path / "Bobine" / "bobine-media")
    assert media.find_binary() == [str(binary.resolve())] or media.find_binary() == [str(binary)]


@pytest.mark.skipif(os.name == "nt", reason="POSIX executable bits")
def test_frozen_macos_bundle_finds_the_binary_in_resources(tmp_path, frozen, monkeypatch):
    monkeypatch.setattr(sys, "executable", str(tmp_path / "Bobine.app" / "Contents" / "MacOS" / "Bobine"))
    (tmp_path / "Bobine.app" / "Contents" / "MacOS").mkdir(parents=True)
    binary = _executable(tmp_path / "Bobine.app" / "Contents" / "Resources" / "bobine-media")
    assert media.find_binary() == [str(binary)]


@pytest.mark.skipif(os.name == "nt", reason="POSIX executable bits")
def test_non_executable_candidate_is_not_selected(tmp_path, frozen, monkeypatch):
    monkeypatch.setattr(sys, "executable", str(tmp_path / "app" / "Bobine"))
    candidate = _executable(tmp_path / "app" / "bobine-media")
    candidate.chmod(0o644)
    assert media.find_binary() is None


@pytest.mark.skipif(os.name == "nt", reason="POSIX signals")
@needs_binary
def test_native_process_exits_when_the_parent_is_killed(tmp_path):
    """EOF on stdin is the only supervision channel: it must also fire when the parent dies."""
    parent = tmp_path / "parent.py"
    parent.write_text(textwrap.dedent(f'''
        import sys, time
        sys.path.insert(0, {str(REPO / "backend")!r})
        from app.utils.media_sidecar import MediaClient
        import wave
        source = {str(tmp_path / "tone.wav")!r}
        with wave.open(source, "wb") as writer:
            writer.setnchannels(1); writer.setsampwidth(2); writer.setframerate(8000)
            writer.writeframes(b"\\0\\0" * 800)
        client = MediaClient([{str(NATIVE)!r}], enabled=True)
        assert client.probe_audio(source, "course-duration-v1") is not None
        print(client._generation.proc.pid, flush=True)
        time.sleep(60)
    '''))
    process = subprocess.Popen([sys.executable, str(parent)], stdout=subprocess.PIPE, text=True)
    try:
        child_pid = int(process.stdout.readline())
        os.kill(child_pid, 0)  # alive while its parent lives
        process.send_signal(signal.SIGKILL)
        process.wait(timeout=5)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                state = Path(f"/proc/{child_pid}/stat").read_text().rsplit(")", 1)[1].split()[0] if sys.platform.startswith("linux") else None
            except FileNotFoundError:
                return
            except ProcessLookupError:
                return
            if state == "Z":  # exited, only waiting to be reaped by init
                return
            if state is None:
                try:
                    os.kill(child_pid, 0)
                except ProcessLookupError:
                    return
            time.sleep(0.05)
        pytest.fail("the native process survived the death of its parent")
    finally:
        if process.poll() is None:
            process.kill()
        process.stdout.close()


@needs_binary
@pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="ffmpeg/ffprobe unavailable")
def test_mp3_durations_match_ffprobe_for_varied_lengths(tmp_path):
    """Regression: raw frame counts over-report by the encoder delay and padding (up to ~52 ms)."""
    client = media.MediaClient([str(NATIVE)], enabled=True)
    try:
        checked = 0
        for index, seconds in enumerate((0.31, 0.73, 1.29, 2.31, 3.07, 4.44, 5.09, 7.77, 9.51, 11.86)):
            for codec in (["-b:a", "128k"], ["-q:a", "3"]):
                path = tmp_path / f"t{index}-{codec[0][1:]}.mp3"
                result = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                                         f"sine=frequency=330:sample_rate=44100:duration={seconds}",
                                         "-c:a", "libmp3lame", *codec, "-write_xing", "1", str(path)],
                                        capture_output=True, timeout=60)
                if result.returncode:
                    pytest.skip("ffmpeg without libmp3lame")
                native = client.probe_audio(path, "course-duration-v1")
                reference = audio_utils.extract_audio_duration(str(path))
                assert native is not None, client.last_failure
                assert reference is not None
                assert abs(native["duration_seconds"] - reference) <= 0.005, (path.name, native, reference)
                checked += 1
        assert checked == 20
    finally:
        client.close()
