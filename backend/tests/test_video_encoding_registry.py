import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.videos.encoding import registry  # noqa: E402
from app.videos.encoding.accelerators.mediacodec import MediaCodec  # noqa: E402
from app.videos.encoding.accelerators.qsv import QuickSync  # noqa: E402
from app.videos.encoding.accelerators.software import Software  # noqa: E402
from app.videos.encoding.accelerators.vaapi import Vaapi  # noqa: E402
from app.videos.encoding.accelerators.videotoolbox import VideoToolbox  # noqa: E402


@pytest.mark.parametrize(("system", "device", "expected"), [
    ("Darwin", None, VideoToolbox), ("Windows", None, QuickSync), ("Linux", "/dev/dri/renderD128", Vaapi),
    ("Linux", None, Software), ("FreeBSD", None, Software),
])
def test_registry_picks_one_accelerator_per_machine(system, device, expected):
    with patch("platform.system", return_value=system), patch.object(registry, "find_vaapi_device", return_value=device):
        assert type(registry.select_accelerator(is_android=False)) is expected


def test_android_always_uses_mediacodec():
    with patch("platform.system", return_value="Linux"):
        assert type(registry.select_accelerator(is_android=True)) is MediaCodec


def test_unknown_android_codec_skips_hardware_decoding():
    tiers = registry.get_transcode_pipeline(True, "mpeg2", 1920, 1080)
    assert [t["name"] for t in tiers] == ["android_mediacodec_hybrid", "software_libx264"]
