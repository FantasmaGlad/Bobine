from pathlib import Path

import pytest

from app.utils.video_utils import normalize

TIERS = [
    {"name": "android_mediacodec_hybrid", "encoder_name": "h264_mediacodec", "hw_in": [], "enc_args": ["-c:v", "h264_mediacodec"]},
    {"name": "software", "encoder_name": "mpeg4", "hw_in": [], "enc_args": ["-c:v", "mpeg4"]},
]
SOURCE = {"duration_seconds": 12.0, "width": 1280, "height": 720, "codec": "wmv2", "audio_codec": None}


@pytest.fixture
def encoders(monkeypatch, tmp_path):
    used: list[str] = []
    outputs: dict[str, dict] = {}

    def run(cmd, job_id, duration, encoder_name=None, width=None, height=None):
        used.append(encoder_name)
        Path(cmd[-1]).write_bytes(b"\0" * 262)
        return 0, ""

    monkeypatch.setattr(normalize, "get_transcode_pipeline", lambda *args: TIERS)
    monkeypatch.setattr(normalize, "run_ffmpeg_with_progress", run)
    monkeypatch.setattr(normalize, "extract_metadata", lambda path: outputs[used[-1]])
    return used, outputs, tmp_path


def test_empty_output_falls_back_to_the_next_encoder(encoders):
    used, outputs, tmp_path = encoders
    outputs["h264_mediacodec"] = {"duration_seconds": None, "codec": None}
    outputs["mpeg4"] = {"duration_seconds": 12.0, "codec": "mpeg4"}
    out = tmp_path / "out.mp4"
    assert normalize.normalize_video(str(tmp_path / "in.wmv"), str(out), ["recode_video"], SOURCE) == str(out)
    assert used == ["h264_mediacodec", "mpeg4"]


def test_import_fails_when_no_encoder_produces_a_video(encoders):
    used, outputs, tmp_path = encoders
    outputs["h264_mediacodec"] = {"duration_seconds": None, "codec": None}
    outputs["mpeg4"] = {"duration_seconds": 0, "codec": "mpeg4"}
    out = tmp_path / "out.mp4"
    with pytest.raises(ValueError, match="sans piste vidéo"):
        normalize.normalize_video(str(tmp_path / "in.wmv"), str(out), ["recode_video"], SOURCE)
    assert not out.exists()


def test_error_message_keeps_the_last_ffmpeg_lines_not_its_banner(monkeypatch, tmp_path):
    banner = "ffmpeg version 8.1.1 Copyright (c) 2000-2026 the FFmpeg developers\n  built with Android clang\n  configuration: --disable-gpl\n"

    def run(cmd, job_id, duration, encoder_name=None, width=None, height=None):
        return 1, banner + "Unknown encoder 'libx264'\nError selecting an encoder\n"

    monkeypatch.setattr(normalize, "get_transcode_pipeline", lambda *args: TIERS[1:])
    monkeypatch.setattr(normalize, "run_ffmpeg_with_progress", run)
    with pytest.raises(ValueError) as error:
        normalize.normalize_video(str(tmp_path / "in.wmv"), str(tmp_path / "out.mp4"), ["recode_video"], SOURCE)
    assert "Unknown encoder 'libx264'" in str(error.value)
    assert "Copyright" not in str(error.value)
