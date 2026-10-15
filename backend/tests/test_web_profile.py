"""Version web « lisible partout » : détection des
raisons de non-lisibilité, négociation selon les capacités annoncées par le
navigateur, et vrai transcodage ffmpeg d'un HEVC 10 bits."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("BOBINE_DATABASE_URL", "sqlite:///data/test_database.db")

from app.utils.web_profile import (  # noqa: E402
    build_web_rendition_command, choose_rendition, client_can_decode, parse_accept, web_playback_issues,
)


# --- raisons de non-lisibilité ---------------------------------------------------

def test_plain_h264_1080p30_is_web_safe():
    assert web_playback_issues("h264", "yuv420p", 1920, 1080, 30.0) == []


def test_h264_1080p60_is_still_safe():
    assert web_playback_issues("h264", "yuv420p", 1920, 1080, 60.0) == []


def test_hevc_is_a_decode_issue():
    assert web_playback_issues("hevc", "yuv420p", 1920, 1080, 30.0) == ["decode:codec-hevc"]


def test_h264_10bit_is_a_pixel_format_issue():
    assert web_playback_issues("h264", "yuv420p10le", 1920, 1080, 30.0) == ["decode:pixel-format"]


def test_uhd_60fps_is_only_a_performance_note():
    issues = web_playback_issues("h264", "yuv420p", 3840, 2160, 60.0)
    assert issues == ["perf:uhd-high-fps"]


def test_unknown_pixel_format_is_not_flagged():
    # vidéos importées avec l'ancienne analyse : tant qu'elles n'ont pas été
    # réanalysées, on ne prétend pas savoir
    assert web_playback_issues("h264", None, 1920, 1080, 30.0) == []


# --- capacités du client ----------------------------------------------------------

def test_client_accepting_hevc_can_play_hevc():
    assert client_can_decode(["decode:codec-hevc"], {"h264", "hevc"}) is True
    assert client_can_decode(["decode:codec-hevc"], {"h264"}) is False


def test_pixel_format_needs_the_hi10_capability():
    assert client_can_decode(["decode:pixel-format"], {"h264"}) is False
    assert client_can_decode(["decode:pixel-format"], {"h264", "hi10"}) is True


def test_performance_notes_never_force_the_web_version():
    assert client_can_decode(["perf:uhd-high-fps"], set()) is True


def test_parse_accept():
    assert parse_accept(None) is None
    assert parse_accept("h264, HEVC,,") == {"h264", "hevc"}
    assert parse_accept("") == set()


# --- choix de la version -----------------------------------------------------------

def _choose(**kw):
    base = dict(issues=["decode:codec-hevc"], web_ready=True, profile=None, accept=None)
    base.update(kw)
    return choose_rendition(**base)


def test_without_negotiation_the_original_is_always_served():
    assert _choose() == "original"


def test_incapable_client_gets_the_web_version_when_ready():
    assert _choose(accept={"h264"}) == "web"


def test_capable_client_keeps_the_original():
    assert _choose(accept={"h264", "hevc"}) == "original"


def test_never_web_when_not_ready_even_if_forced():
    assert _choose(accept={"h264"}, web_ready=False) == "original"
    assert _choose(profile="web", web_ready=False) == "original"


def test_explicit_profile_overrides_negotiation():
    assert _choose(profile="web", accept={"h264", "hevc"}) == "web"
    assert _choose(profile="original", accept={"h264"}) == "original"


# --- ligne de commande ffmpeg ---------------------------------------------------------

def test_command_downscales_uhd_and_caps_frame_rate():
    cmd = build_web_rendition_command("ffmpeg", "in.mkv", "out.mp4", 2160, 120.0, has_audio=True)
    vf = cmd[cmd.index("-vf") + 1]
    assert "scale=-2:1080" in vf and "fps=60" in vf
    assert "-pix_fmt" in cmd and cmd[cmd.index("-pix_fmt") + 1] == "yuv420p"
    assert cmd[-1] == "out.mp4" and "+faststart" in cmd


def test_command_without_audio_has_no_audio_flags():
    cmd = build_web_rendition_command("ffmpeg", "in.mkv", "out.mp4", 1080, 30.0, has_audio=False)
    assert "-c:a" not in cmd and "-vf" not in cmd


@pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None, reason="ffmpeg absent")
def test_real_transcode_of_hevc_10bit_gives_a_safe_h264(tmp_path):
    source = tmp_path / "src.mkv"
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30",
         "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000", "-t", "2",
         "-c:v", "libx265", "-preset", "ultrafast", "-x265-params", "log-level=error",
         "-pix_fmt", "yuv420p10le", "-c:a", "ac3", str(source)],
        check=True,
    )
    output = tmp_path / "web.mp4"
    subprocess.run(build_web_rendition_command("ffmpeg", str(source), str(output), 720, 30.0, True), check=True)
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name,pix_fmt,profile",
         "-of", "csv=p=0", str(output)], capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert probe.startswith("h264,High,yuv420p")
    audio = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=codec_name,channels",
         "-of", "csv=p=0", str(output)], capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert audio == "aac,2"
