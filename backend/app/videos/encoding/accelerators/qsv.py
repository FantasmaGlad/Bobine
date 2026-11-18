from ..tiers import GOP, hardware_tiers

ENCODER = "h264_qsv"


def _args(bitrate: str) -> list[str]:
    return ["-c:v", ENCODER, "-preset", "fast", "-b:v", bitrate]


class QuickSync:
    def encoder_args(self, bitrate: str) -> tuple[list[str], str]:
        return [*_args(bitrate), *GOP], ENCODER

    def tiers(self, in_codec: str, bitrate: str) -> list[dict]:
        return hardware_tiers("qsv", ENCODER, ["-hwaccel", "qsv", "-hwaccel_output_format", "qsv"], _args(bitrate))
