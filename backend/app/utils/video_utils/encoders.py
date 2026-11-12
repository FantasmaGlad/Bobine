"""Choix de l'encodeur et de la chaîne de transcodage selon la machine."""
import os
import subprocess
import logging
import platform
from pathlib import Path


logger = logging.getLogger(__name__)


def get_target_bitrate(width: int | None, height: int | None) -> str:
    """
    Calcule un débit binaire adapté garantissant une qualité vidéo native intégrale
    sans aucune réduction (downscale) de résolution (conservation 2K/4K).
    """
    w = width or 1920
    h = height or 1080
    pixels = w * h
    if pixels >= 3840 * 2160 * 0.8:  # 4K UHD (2160p)
        return "28M"
    elif pixels >= 2560 * 1440 * 0.8:  # 2K QHD (1440p)
        return "14M"
    return "6M"  # 1080p Full HD et inférieur


def find_vaapi_device() -> str | None:
    """
    Recherche un périphérique DRM render node disponible et accessible en lecture/écriture.
    Priorité aux noeuds conventionnels renderD128 et renderD129, puis balayage de /dev/dri/renderD*.
    """
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
    """
    Détermine les arguments d'encodage optimaux selon la plateforme et le matériel détecté.
    Retourne (liste_arguments_ffmpeg, nom_encodeur).
    """
    bitrate = get_target_bitrate(width, height)
    system = platform.system().lower()

    # Intervalle de trames clés resserré : sans `-g` explicite, ffmpeg choisit un GOP par défaut
    # pouvant dépasser plusieurs secondes — un seek admin vers une position
    # hors keyframe oblige alors le décodeur à rattraper depuis la keyframe
    # précédente, terrain propice aux blocages sur certains décodeurs
    # matériels (VA-API, MediaCodec). Une trame clé toutes les 60 images
    # (~2s à 30 im/s) borne ce rattrapage sans impact perceptible sur le
    # débit à ces bitrates cibles.
    gop_args = ["-g", "60"]

    if is_android:
        # Qualcomm Snapdragon MediaCodec matériel : operating_rate 1000 pour horloge max,
        # nv12 pour zéro-copie avec le décodeur matériel.
        return (["-c:v", "h264_mediacodec", "-operating_rate", "1000", "-pix_fmt", "nv12", "-b:v", bitrate, *gop_args], "h264_mediacodec")

    if system == "darwin":
        # macOS : Apple Silicon (puces M1/M2/M3/M4) et Intel via VideoToolbox matériel
        return (["-c:v", "h264_videotoolbox", "-q:v", "65", "-pix_fmt", "yuv420p", *gop_args], "h264_videotoolbox")

    if system == "linux":
        # Dell Wyse 5070 (Intel Gemini Lake UHD 600) ou station Linux avec VA-API
        dev = find_vaapi_device()
        if dev:
            return (["-vaapi_device", dev, "-vf", "format=nv12,hwupload", "-c:v", "h264_vaapi", "-async_depth", "4", "-b:v", bitrate, *gop_args], "h264_vaapi")

    if system == "windows":
        # Windows : Intel QuickSync (h264_qsv)
        return (["-c:v", "h264_qsv", "-preset", "fast", "-b:v", bitrate, *gop_args], "h264_qsv")

    # Repli logiciel universel haute compatibilité (serveurs headless sans GPU, repli après échec GPU)
    # Race to sleep : preset ultrafast et tous les threads CPU disponibles (-threads 0) pour achever la tâche au plus vite
    return (["-c:v", "libx264", "-preset", "ultrafast", "-crf", "20", "-threads", "0", "-pix_fmt", "yuv420p", *gop_args, "-keyint_min", "60"], "libx264")


def get_transcode_pipeline(
    is_android: bool,
    in_codec: str,
    width: int | None,
    height: int | None,
) -> list[dict]:
    """
    Construit le pipeline d'accélération matérielle multi-paliers (Full HW -> Hybride -> Logiciel).
    Chaque palier est un dictionnaire contenant :
    - 'name': identifiant lisible du palier
    - 'encoder_name': nom de l'encodeur (pour les statistiques de vitesse)
    - 'hw_in': liste d'arguments placés AVANT -i (décodage matériel GPU direct en VRAM)
    - 'enc_args': liste d'arguments d'encodage vidéo placés APRÈS -i
    """
    bitrate = get_target_bitrate(width, height)
    system = platform.system().lower()
    gop_args = ["-g", "60"]
    sw_tier = {
        "name": "software_libx264",
        "encoder_name": "libx264",
        "hw_in": [],
        "enc_args": ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "20", "-threads", "0", "-pix_fmt", "yuv420p", *gop_args, "-keyint_min", "60"],
    }

    if is_android:
        android_decoders = {
            "av1": "av1_mediacodec",
            "hevc": "hevc_mediacodec",
            "h265": "hevc_mediacodec",
            "vp9": "vp9_mediacodec",
            "h264": "h264_mediacodec",
        }
        dec = android_decoders.get(in_codec)
        tiers = []
        if dec:
            tiers.append({
                "name": "android_mediacodec_full",
                "encoder_name": "h264_mediacodec",
                "hw_in": ["-operating_rate", "1000", "-c:v", dec],
                "enc_args": ["-c:v", "h264_mediacodec", "-operating_rate", "1000", "-pix_fmt", "nv12", "-b:v", bitrate, *gop_args],
            })
        tiers.append({
            "name": "android_mediacodec_hybrid",
            "encoder_name": "h264_mediacodec",
            "hw_in": [],
            "enc_args": ["-c:v", "h264_mediacodec", "-operating_rate", "1000", "-pix_fmt", "nv12", "-b:v", bitrate, *gop_args],
        })
        tiers.append(sw_tier)
        return tiers

    if system == "darwin":
        return [
            {
                "name": "videotoolbox_full",
                "encoder_name": "h264_videotoolbox",
                "hw_in": ["-hwaccel", "videotoolbox"],
                "enc_args": ["-c:v", "h264_videotoolbox", "-q:v", "65", "-pix_fmt", "yuv420p", *gop_args],
            },
            {
                "name": "videotoolbox_hybrid",
                "encoder_name": "h264_videotoolbox",
                "hw_in": [],
                "enc_args": ["-c:v", "h264_videotoolbox", "-q:v", "65", "-pix_fmt", "yuv420p", *gop_args],
            },
            sw_tier,
        ]

    if system == "linux":
        vaapi_dev = find_vaapi_device()
        if vaapi_dev:
            return [
                {
                    "name": "vaapi_full",
                    "encoder_name": "h264_vaapi",
                    "hw_in": ["-hwaccel", "vaapi", "-hwaccel_device", vaapi_dev, "-hwaccel_output_format", "vaapi"],
                    "enc_args": ["-vf", "scale_vaapi=format=nv12", "-c:v", "h264_vaapi", "-async_depth", "4", "-b:v", bitrate, *gop_args],
                },
                {
                    "name": "vaapi_hybrid",
                    "encoder_name": "h264_vaapi",
                    "hw_in": [],
                    "enc_args": ["-vaapi_device", vaapi_dev, "-vf", "format=nv12,hwupload", "-c:v", "h264_vaapi", "-async_depth", "4", "-b:v", bitrate, *gop_args],
                },
                sw_tier,
            ]

    if system == "windows":
        return [
            {
                "name": "qsv_full",
                "encoder_name": "h264_qsv",
                "hw_in": ["-hwaccel", "qsv", "-hwaccel_output_format", "qsv"],
                "enc_args": ["-c:v", "h264_qsv", "-preset", "fast", "-b:v", bitrate, *gop_args],
            },
            {
                "name": "qsv_hybrid",
                "encoder_name": "h264_qsv",
                "hw_in": [],
                "enc_args": ["-c:v", "h264_qsv", "-preset", "fast", "-b:v", bitrate, *gop_args],
            },
            sw_tier,
        ]

    return [sw_tier]


def shares_machine_with_browser() -> bool:
    """Vrai sur les profils où le navigateur d'administration tourne sur la
    MÊME machine que le backend (applications Windows, macOS et Linux de
    bureau) : un réencodage `-threads 0` au plein de la priorité y affame le
    navigateur (onglet figé, voire tué par manque de mémoire/CPU). Faux sur
    l'appliance headless dédiée (le « race to sleep » reste voulu : finir
    vite pour redormir) et sur Android (cf. profil dédié, seccomp)."""
    from app.utils.deployment import get_deployment_profile

    return get_deployment_profile() in ("windows", "macos", "linux-desktop")


def background_priority_popen_kwargs() -> dict:
    """Windows : classe de priorité « sous la normale » dès la création."""
    if os.name == "nt" and shares_machine_with_browser():
        return {"creationflags": getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)}
    return {}


def lower_process_priority(pid: int) -> None:
    """POSIX (macOS, Linux de bureau) : `nice 10` sur le processus ffmpeg. Posé
    juste après le lancement plutôt que par `preexec_fn`, déconseillé dans un
    processus multi-threadé (risque d'interblocage). Best-effort : un échec ne
    doit jamais faire échouer l'import."""
    if os.name == "nt" or not shares_machine_with_browser():
        return
    try:
        os.setpriority(os.PRIO_PROCESS, pid, 10)
    except (OSError, AttributeError) as e:
        logger.debug(f"Priorité réduite de ffmpeg impossible (pid {pid}) : {e}")
