"""Choix de l'encodeur et de la chaîne de transcodage selon la machine."""
import os
import subprocess
import logging
import platform
from pathlib import Path


logger = logging.getLogger(__name__)


def get_target_bitrate(width: int | None, height: int | None) -> str:
    """Calcule un débit binaire adapté garantissant une qualité vidéo native intégrale sans aucune réduction (downscale) de résolution (conservation 2K/4K)."""
    w = width or 1920
    h = height or 1080
    pixels = w * h
    if pixels >= 3840 * 2160 * 0.8:
        return "28M"
    elif pixels >= 2560 * 1440 * 0.8:
        return "14M"
    return "6M"


def find_vaapi_device() -> str | None:
    """Recherche un périphérique DRM render node disponible et accessible en lecture/écriture."""
    candidates = ["/dev/dri/renderD128", "/dev/dri/renderD129"]
    dri_dir = Path("/dev/dri")
    if dri_dir.exists():
        try:
            for p in dri_dir.glob("renderD*"):
                sp = str(p)
                if sp not in candidates:
                    candidates.append(sp)
        except OSError:
            pass

    for dev in candidates:
        if os.path.exists(dev) and os.access(dev, os.R_OK | os.W_OK):
            return dev
    return None


def get_encoder_args(is_android: bool, width: int | None, height: int | None) -> tuple[list[str], str]:
    """Détermine les arguments d'encodage optimaux selon la plateforme et le matériel détecté."""
    bitrate = get_target_bitrate(width, height)
    system = platform.system().lower()

    gop_args = ["-g", "60"]

    if is_android:
        return (["-c:v", "h264_mediacodec", "-operating_rate", "1000", "-pix_fmt", "nv12", "-b:v", bitrate, *gop_args], "h264_mediacodec")

    if system == "darwin":
        return (["-c:v", "h264_videotoolbox", "-q:v", "65", "-pix_fmt", "yuv420p", *gop_args], "h264_videotoolbox")

    if system == "linux":
        dev = find_vaapi_device()
        if dev:
            return (["-vaapi_device", dev, "-vf", "format=nv12,hwupload", "-c:v", "h264_vaapi", "-async_depth", "4", "-b:v", bitrate, *gop_args], "h264_vaapi")

    if system == "windows":
        return (["-c:v", "h264_qsv", "-preset", "fast", "-b:v", bitrate, *gop_args], "h264_qsv")

    return (["-c:v", "libx264", "-preset", "ultrafast", "-crf", "20", "-threads", "0", "-pix_fmt", "yuv420p", *gop_args, "-keyint_min", "60"], "libx264")


_GOP = ["-g", "60"]
_ANDROID_DECODERS = {"av1": "av1_mediacodec", "hevc": "hevc_mediacodec", "h265": "hevc_mediacodec",
                     "vp9": "vp9_mediacodec", "h264": "h264_mediacodec"}
_SOFTWARE_TIER = {
    "name": "software_libx264",
    "encoder_name": "libx264",
    "hw_in": [],
    "enc_args": ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "20", "-threads", "0", "-pix_fmt", "yuv420p", *_GOP, "-keyint_min", "60"],
}


def _tier(name: str, encoder: str, hw_in: list[str], enc_args: list[str]) -> dict:
    return {"name": name, "encoder_name": encoder, "hw_in": hw_in, "enc_args": [*enc_args, *_GOP]}


def _pair(prefix: str, encoder: str, hw_in: list[str], enc_args: list[str], hybrid_args: list[str] | None = None) -> list[dict]:
    return [_tier(f"{prefix}_full", encoder, hw_in, enc_args),
            _tier(f"{prefix}_hybrid", encoder, [], hybrid_args or enc_args),
            dict(_SOFTWARE_TIER)]


def _android_tiers(in_codec: str, bitrate: str) -> list[dict]:
    args = ["-c:v", "h264_mediacodec", "-operating_rate", "1000", "-pix_fmt", "nv12", "-b:v", bitrate]
    decoder = _ANDROID_DECODERS.get(in_codec)
    tiers = _pair("android_mediacodec", "h264_mediacodec", ["-operating_rate", "1000", "-c:v", decoder or ""], args)
    return tiers if decoder else tiers[1:]


def _vaapi_tiers(device: str, bitrate: str) -> list[dict]:
    return _pair("vaapi", "h264_vaapi", ["-hwaccel", "vaapi", "-hwaccel_device", device, "-hwaccel_output_format", "vaapi"],
                 ["-vf", "scale_vaapi=format=nv12", "-c:v", "h264_vaapi", "-async_depth", "4", "-b:v", bitrate],
                 ["-vaapi_device", device, "-vf", "format=nv12,hwupload", "-c:v", "h264_vaapi", "-async_depth", "4", "-b:v", bitrate])


def get_transcode_pipeline(
    is_android: bool,
    in_codec: str,
    width: int | None,
    height: int | None,
) -> list[dict]:
    """Construit le pipeline d'accélération matérielle multi-paliers (Full HW -> Hybride -> Logiciel)."""
    bitrate = get_target_bitrate(width, height)
    system = platform.system().lower()
    if is_android:
        return _android_tiers(in_codec, bitrate)
    if system == "darwin":
        return _pair("videotoolbox", "h264_videotoolbox", ["-hwaccel", "videotoolbox"],
                     ["-c:v", "h264_videotoolbox", "-q:v", "65", "-pix_fmt", "yuv420p"])
    if system == "linux":
        device = find_vaapi_device()
        if device:
            return _vaapi_tiers(device, bitrate)
    if system == "windows":
        return _pair("qsv", "h264_qsv", ["-hwaccel", "qsv", "-hwaccel_output_format", "qsv"],
                     ["-c:v", "h264_qsv", "-preset", "fast", "-b:v", bitrate])
    return [dict(_SOFTWARE_TIER)]


def shares_machine_with_browser() -> bool:
    """Vrai sur les profils où le navigateur d'administration tourne sur la MÊME machine que le backend."""
    from app.utils.deployment import get_deployment_profile

    return get_deployment_profile() in ("windows", "macos", "linux-desktop")


def background_priority_popen_kwargs() -> dict:
    """Windows : classe de priorité « sous la normale » dès la création."""
    if os.name == "nt" and shares_machine_with_browser():
        return {"creationflags": getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)}
    return {}


def lower_process_priority(pid: int) -> None:
    """POSIX (macOS, Linux de bureau) : `nice 10` sur le processus ffmpeg."""
    if os.name == "nt" or not shares_machine_with_browser():
        return
    try:
        os.setpriority(os.PRIO_PROCESS, pid, 10)
    except (OSError, AttributeError) as e:
        logger.debug(f"Priorité réduite de ffmpeg impossible (pid {pid}) : {e}")
