from ..tiers import GOP, hardware_tiers

ENCODER = "h264_videotoolbox"
_ARGS = ["-c:v", ENCODER, "-q:v", "65", "-pix_fmt", "yuv420p"]


class VideoToolbox:
    def encoder_args(self, bitrate: str) -> tuple[list[str], str]:
        return [*_ARGS, *GOP], ENCODER

    def tiers(self, in_codec: str, bitrate: str) -> list[dict]:
        return hardware_tiers("videotoolbox", ENCODER, ["-hwaccel", "videotoolbox"], _ARGS)
