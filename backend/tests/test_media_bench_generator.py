"""Pure parts of the audio corpus generator used by the native component bench."""
import importlib.util
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def generator():
    spec = importlib.util.spec_from_file_location("media_bench_generate", ROOT / "scripts" / "media-bench" / "generate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _synthetic_mp3(frames=5, id3_size=0):
    """MPEG-1 Layer III, 44.1 kHz, 128 kbit/s, no CRC: 417-byte frames."""
    tag = b""
    if id3_size:
        syncsafe = bytes((id3_size >> 21 & 0x7F, id3_size >> 14 & 0x7F, id3_size >> 7 & 0x7F, id3_size & 0x7F))
        tag = b"ID3\x04\x00\x00" + syncsafe + b"\0" * id3_size
    return tag + (b"\xff\xfb\x90\x00" + b"\x55" * 413) * frames


def test_vbri_frame_is_inserted_after_the_id3_tag_with_exact_counts(generator):
    source = _synthetic_mp3(frames=5, id3_size=20)
    result = generator.build_vbri_mp3(source)
    start = 10 + 20
    assert len(result) == len(source) + 417
    assert result[:start] == source[:start]
    assert result[start + 36:start + 40] == b"VBRI"
    assert int.from_bytes(result[start + 40:start + 42], "big") == 1  # tag version
    assert int.from_bytes(result[start + 46:start + 50], "big") == 5 * 417  # audio bytes
    assert int.from_bytes(result[start + 50:start + 54], "big") == 5  # frames
    # The original audio is untouched and still follows the inserted frame.
    assert result[start + 417:] == source[start:]
    assert b"Xing" not in result and b"Info" not in result


def test_vbri_requires_mpeg_audio(generator):
    with pytest.raises(ValueError):
        generator.build_vbri_mp3(b"not an mp3" * 10)
    with pytest.raises(ValueError):
        generator.build_vbri_mp3(b"ID3\x04\x00\x00\x00\x00\x00\x00")


@pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="ffmpeg/ffprobe unavailable")
def test_ffprobe_reads_the_synthesized_vbri_duration(generator, tmp_path):
    cbr = tmp_path / "cbr.mp3"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "sine=duration=2.0",
                    "-c:a", "libmp3lame", "-b:a", "128k", "-write_xing", "0", str(cbr)], check=True, timeout=60)
    data = cbr.read_bytes()
    start = 0
    if data[:3] == b"ID3":
        start = 10 + (data[6] << 21 | data[7] << 14 | data[8] << 7 | data[9])
    _, frames = generator._mp3_frames(data, start)
    vbri = tmp_path / "vbri.mp3"
    vbri.write_bytes(generator.build_vbri_mp3(data))
    probed = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(vbri)],
                            capture_output=True, text=True, check=True, timeout=30)
    # VBRI makes ffprobe use the frame count rather than the bitrate-based estimate.
    assert float(probed.stdout) == pytest.approx(len(frames) * 1152 / 44100, abs=1e-5)
