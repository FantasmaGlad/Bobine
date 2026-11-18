import os
from pathlib import Path

from ..tiers import GOP, hardware_tiers

ENCODER = "h264_vaapi"


def find_vaapi_device() -> str | None:
    """Premier nœud de rendu DRM accessible en lecture et écriture."""
    candidates = ["/dev/dri/renderD128", "/dev/dri/renderD129"]
    dri_dir = Path("/dev/dri")
    if dri_dir.exists():
        try:
            for p in dri_dir.glob("renderD*"):
                if str(p) not in candidates:
                    candidates.append(str(p))
        except OSError:
            pass
    return next((dev for dev in candidates if os.path.exists(dev) and os.access(dev, os.R_OK | os.W_OK)), None)


class Vaapi:
    def __init__(self, device: str):
        self.device = device

    def _upload_args(self, bitrate: str) -> list[str]:
        return ["-vaapi_device", self.device, "-vf", "format=nv12,hwupload", "-c:v", ENCODER, "-async_depth", "4", "-b:v", bitrate]

    def encoder_args(self, bitrate: str) -> tuple[list[str], str]:
        return [*self._upload_args(bitrate), *GOP], ENCODER

    def tiers(self, in_codec: str, bitrate: str) -> list[dict]:
        return hardware_tiers("vaapi", ENCODER,
                              ["-hwaccel", "vaapi", "-hwaccel_device", self.device, "-hwaccel_output_format", "vaapi"],
                              ["-vf", "scale_vaapi=format=nv12", "-c:v", ENCODER, "-async_depth", "4", "-b:v", bitrate],
                              self._upload_args(bitrate))
