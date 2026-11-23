import shutil
import subprocess
from pathlib import Path

import pytest

from app.utils import image_decode
from app.utils.image_decode import android, ffmpeg_still, registry
from app.utils.importer import background


def test_heif_needs_ffmpeg_7_1_or_a_development_build():
    assert ffmpeg_still.supports_heif("ffmpeg version 8.0.1-3ubuntu2 Copyright (c) 2000-2025")
    assert ffmpeg_still.supports_heif("ffmpeg version 7.1 Copyright")
    assert ffmpeg_still.supports_heif("ffmpeg version n7.1.1 Copyright")
    assert ffmpeg_still.supports_heif("ffmpeg version N-128227-g4811625b5f-20260101 Copyright")
    assert not ffmpeg_still.supports_heif("ffmpeg version 6.1.1-3ubuntu5 Copyright")
    assert not ffmpeg_still.supports_heif("ffmpeg version 7.0.2 Copyright")
    assert not ffmpeg_still.supports_heif("")


def test_android_sample_size_keeps_images_under_the_pixel_bound():
    assert android.sample_size(4000, 3000) == 1
    assert android.sample_size(12000, 9000) == 2
    assert android.sample_size(24000, 18000) == 4


def test_registry_picks_the_android_decoder_on_android():
    assert registry.platform_decoder("android") is android.decode
    assert registry.platform_decoder("linux-desktop") is ffmpeg_still.decode


def test_heic_is_refused_with_an_old_ffmpeg(monkeypatch, tmp_path):
    monkeypatch.setattr(ffmpeg_still, "_version_line", lambda: "ffmpeg version 6.1.1 Copyright")
    with pytest.raises(ValueError, match="7.1"):
        ffmpeg_still.decode(tmp_path / "a.heic", tmp_path / "a.png", ".heic")


def test_a_decoder_without_output_is_an_error(monkeypatch, tmp_path):
    monkeypatch.setattr(image_decode, "platform_decoder", lambda: lambda source, dest, ext: None)
    source = tmp_path / "x.avif"
    source.write_bytes(b"not an image")
    with pytest.raises(ValueError, match="aucune image"):
        image_decode.decode_to_png(source, "x.avif")


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg absent")
def test_avif_unread_by_pillow_is_converted_through_the_platform_decoder(monkeypatch, tmp_path):
    source = tmp_path / "pic.avif"
    made = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=320x180",
                           "-frames:v", "1", "-c:v", "libaom-av1", "-still-picture", "1", str(source)], capture_output=True)
    if made.returncode != 0 or not source.exists():
        pytest.skip("encodeur AV1 absent de ce ffmpeg")
    from PIL import Image

    real_open = Image.open

    def pillow_without_avif(path, *args, **kwargs):
        if str(path).endswith(".avif"):
            raise OSError("cannot identify image file")
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(Image, "open", pillow_without_avif)
    decoded = background._decoded_by_platform(source, "pic.avif", OSError("cannot identify image file"))
    assert decoded.suffix == ".png"
    assert not source.exists()
    with real_open(decoded) as img:
        assert img.size == (320, 180)


def test_a_png_that_pillow_cannot_read_is_not_sent_to_the_platform_decoder(tmp_path):
    with pytest.raises(ValueError, match="pas une image valide"):
        background._decoded_by_platform(tmp_path / "broken.png", "broken.png", OSError("truncated"))
    assert not Path(tmp_path / "broken.png.decoded.png").exists()
