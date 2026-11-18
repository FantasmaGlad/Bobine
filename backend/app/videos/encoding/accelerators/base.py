from typing import Protocol


class Accelerator(Protocol):
    def encoder_args(self, bitrate: str) -> tuple[list[str], str]: ...

    def tiers(self, in_codec: str, bitrate: str) -> list[dict]: ...
