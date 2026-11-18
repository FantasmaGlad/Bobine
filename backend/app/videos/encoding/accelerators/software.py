from ..tiers import SOFTWARE_TIER


class Software:
    def encoder_args(self, bitrate: str) -> tuple[list[str], str]:
        return list(SOFTWARE_TIER["enc_args"]), SOFTWARE_TIER["encoder_name"]

    def tiers(self, in_codec: str, bitrate: str) -> list[dict]:
        return [dict(SOFTWARE_TIER)]
