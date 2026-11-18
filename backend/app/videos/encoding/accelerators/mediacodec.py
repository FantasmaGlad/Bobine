from ..tiers import GOP, hardware_tiers

ENCODER = "h264_mediacodec"
_DECODERS = {"av1": "av1_mediacodec", "hevc": "hevc_mediacodec", "h265": "hevc_mediacodec",
             "vp9": "vp9_mediacodec", "h264": "h264_mediacodec"}


def _args(bitrate: str) -> list[str]:
    return ["-c:v", ENCODER, "-operating_rate", "1000", "-pix_fmt", "nv12", "-b:v", bitrate]


class MediaCodec:
    def encoder_args(self, bitrate: str) -> tuple[list[str], str]:
        return [*_args(bitrate), *GOP], ENCODER

    def tiers(self, in_codec: str, bitrate: str) -> list[dict]:
        decoder = _DECODERS.get(in_codec)
        tiers = hardware_tiers("android_mediacodec", ENCODER, ["-operating_rate", "1000", "-c:v", decoder or ""], _args(bitrate))
        return tiers if decoder else tiers[1:]
