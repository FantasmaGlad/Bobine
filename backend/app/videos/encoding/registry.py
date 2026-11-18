import platform

from .accelerators.base import Accelerator
from .accelerators.mediacodec import MediaCodec
from .accelerators.qsv import QuickSync
from .accelerators.software import Software
from .accelerators.vaapi import Vaapi, find_vaapi_device
from .accelerators.videotoolbox import VideoToolbox
from .bitrate import get_target_bitrate


def select_accelerator(is_android: bool) -> Accelerator:
    if is_android:
        return MediaCodec()
    system = platform.system().lower()
    if system == "darwin":
        return VideoToolbox()
    if system == "linux":
        device = find_vaapi_device()
        if device:
            return Vaapi(device)
    if system == "windows":
        return QuickSync()
    return Software()


def get_encoder_args(is_android: bool, width: int | None, height: int | None) -> tuple[list[str], str]:
    """Arguments d'encodage de l'accélérateur retenu et nom de l'encodeur."""
    return select_accelerator(is_android).encoder_args(get_target_bitrate(width, height))


def get_transcode_pipeline(is_android: bool, in_codec: str, width: int | None, height: int | None) -> list[dict]:
    """Paliers de transcodage de l'accélérateur retenu, du plus matériel au logiciel."""
    return select_accelerator(is_android).tiers(in_codec, get_target_bitrate(width, height))
