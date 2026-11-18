"""Choix de l'encodeur et des paliers de transcodage selon la machine."""
from .bitrate import get_target_bitrate
from .registry import get_encoder_args, get_transcode_pipeline, select_accelerator

__all__ = ["get_encoder_args", "get_target_bitrate", "get_transcode_pipeline", "select_accelerator"]
