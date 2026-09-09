import os
import subprocess
import json
import logging
import uuid
import time
import platform
from pathlib import Path

from app.utils.ffmpeg_binaries import FFMPEG_BIN, FFPROBE_BIN

logger = logging.getLogger(__name__)


# Délai maximum accordé à chaque appel ffprobe/ffmpeg (réf. retour
# utilisateur "l'importation des fonds animés bloque et ne termine jamais") :
# ces appels tournent sur l'exécuteur mono-thread PARTAGÉ par tous les imports
# de l'application (app.utils.executors.ffmpeg_executor) — un seul fichier
# problématique (corrompu, flux exotique sur lequel ffmpeg reste bloqué en
# lecture) y bloquerait alors indéfiniment TOUS les imports suivants, upload
# comme dossier surveillé, sans jamais remonter d'erreur ni libérer le
# thread. Un timeout transforme ce blocage silencieux en échec explicite.
FFPROBE_TIMEOUT_SECONDS = 30
FFMPEG_THUMBNAIL_TIMEOUT_SECONDS = 30
# Plus généreux que les deux ci-dessus (réf. constat en production : un
# réencodage réel de vidéo musicale complète de plusieurs minutes, soumise
# comme fond animé, a mis plus de 15 min à se terminer en logiciel pur sur le
# CPU modeste du Wyse 5070) : laisse la place à un réencodage légitimement
# long tout en bornant le pire cas (fichier corrompu/pathologique).
FFMPEG_NORMALIZE_TIMEOUT_SECONDS = 1800

def get_video_info(file_path: str) -> dict:
    """
    Exécute ffprobe pour extraire les informations de flux et de format de la vidéo au format JSON.
    """
    cmd = [
        FFPROBE_BIN,
        "-v", "error",
        "-show_entries", "format=duration",
        "-show_streams",
        "-print_format", "json",
        file_path
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=FFPROBE_TIMEOUT_SECONDS)
        return json.loads(res.stdout)
    except subprocess.TimeoutExpired:
        logger.error(f"ffprobe : délai dépassé ({FFPROBE_TIMEOUT_SECONDS}s) pour {file_path}")
        raise ValueError(f"L'analyse du fichier vidéo a dépassé {FFPROBE_TIMEOUT_SECONDS}s (ffprobe)")
    except subprocess.CalledProcessError as e:
        logger.error(f"ffprobe failed for {file_path}: {e.stderr}")
        raise ValueError(f"Impossible de lire le fichier vidéo avec ffprobe : {e.stderr}")
    except Exception as e:
        logger.error(f"Error running ffprobe for {file_path}: {e}")
        raise ValueError(f"Erreur lors de la lecture des métadonnées : {str(e)}")


def extract_metadata(file_path: str) -> dict:
    """
    Extrait les métadonnées pertinentes (durée, résolution, codecs, DRM) du fichier vidéo.
    """
    info = get_video_info(file_path)
    streams = info.get("streams", [])
    fmt = info.get("format", {})

    duration = None
    if "duration" in fmt:
        try:
            duration = float(fmt["duration"])
        except ValueError:
            pass

    v_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    a_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    width = None
    height = None
    v_codec = None
    if v_stream:
        width = v_stream.get("width")
        height = v_stream.get("height")
        v_codec = v_stream.get("codec_name")
        if duration is None and "duration" in v_stream:
            try:
                duration = float(v_stream["duration"])
            except ValueError:
                pass

    a_codec = None
    if a_stream:
        a_codec = a_stream.get("codec_name")

    # Détection des DRM (FairPlay / Encrypted streams)
    is_drm = False
    for s in streams:
        c_name = str(s.get("codec_name", "")).lower()
        c_tag = str(s.get("codec_tag_string", "")).lower()
        # "encv" et "enca" indiquent des flux chiffrés standard dans les conteneurs MP4/ISO
        if c_name in ("encv", "enca") or c_tag in ("encv", "enca"):
            is_drm = True
            break

    # Vérification des tags pour détecter des mentions de DRM ou chiffrement
    if not is_drm:
        for s in streams:
            for k, v in s.get("tags", {}).items():
                if "encryption" in k.lower() or "drm" in k.lower():
                    is_drm = True
                    break
            if is_drm:
                break

    return {
        "duration_seconds": duration,
        "width": width,
        "height": height,
        "codec": v_codec,
        "audio_codec": a_codec,
        "is_drm": is_drm
    }


# Codecs vidéo dont la robustesse a été validée sur le Wyse 5070 (Lot 0).
# Restreint à H.264 pour l'instant (réf. audit plan-corrections-bugs, point
# 6) : HEVC/VP9 ont été validés en lecture continue mais pas spécifiquement
# en boucle (un fond animé redémarre le décodeur toutes les quelques
# secondes, sollicitation plus dure qu'une lecture linéaire) — à élargir
# seulement après un vrai test de boucle sur le matériel cible.
COMPATIBLE_VIDEO_CODECS = {"h264"}

# Codecs supplémentaires validés pour une vidéo de COURS (lue une seule fois,
# en continu — jamais en boucle) : plus permissive que la liste stricte
# ci-dessus, réservée aux fonds animés. Réf. correctif "un cours mal encodé
# peut être importé sans avertissement puis échouer à la lecture" — avant ce
# correctif, `strict_video_codec=False` ne rétrécissait pas cette liste, il
# sautait la vérification du codec vidéo EN ENTIER (n'importe quel codec,
# même jamais testé sur ce matériel — AV1, MPEG-2, VC-1...— passait pour
# "compatible"). Un cours dans un codec hors de cette liste déclenche
# maintenant un réencodage à l'import, comme pour un fond animé non conforme,
# plutôt que d'être importé tel quel sans avertissement.
COMPATIBLE_COURSE_VIDEO_CODECS = COMPATIBLE_VIDEO_CODECS | {"hevc", "vp9"}


def is_faststart_mp4(file_path: str) -> bool:
    """
    Vrai si l'atome 'moov' (index des échantillons) précède l'atome 'mdat'
    (données) dans le fichier — condition requise pour qu'un navigateur
    puisse décoder la moindre image avant d'avoir reçu la quasi-totalité du
    fichier (réf. correctif "critique kiosk/réseau — reste figé sur la
    première frame"). ffmpeg écrit 'moov' APRÈS 'mdat' par défaut (à la toute
    fin du fichier) sauf option explicite `-movflags +faststart` : invisible
    en boucle localhost (l'écran câblé récupère la fin du fichier quasi
    instantanément via Range), mais un lecteur sur une vraie liaison LAN/WiFi
    doit alors télécharger presque tout le fichier — souvent plusieurs
    centaines de Mo pour un cours — avant de pouvoir peindre une seule image.

    Ne lit que les en-têtes de boîtes top-level (8 ou 16 octets chacune),
    jamais leur contenu : coût constant quelle que soit la taille du fichier.
    """
    try:
        with open(file_path, "rb") as f:
            file_size = os.fstat(f.fileno()).st_size
            pos = 0
            while pos < file_size:
                header = f.read(8)
                if len(header) < 8:
                    break
                size = int.from_bytes(header[0:4], "big")
                box_type = header[4:8].decode("ascii", errors="ignore")
                if box_type == "moov":
                    return True
                if box_type == "mdat":
                    return False
                if size == 1:
                    # Boîte 64 bits : la taille réelle suit l'en-tête normal.
                    ext = f.read(8)
                    if len(ext) < 8:
                        break
                    size = int.from_bytes(ext, "big")
                elif size == 0:
                    # Dernière boîte du fichier, s'étend jusqu'à la fin.
                    break
                if size < 8:
                    break
                pos += size
                f.seek(pos)
    except OSError as e:
        logger.warning(f"Impossible de vérifier l'ordre des atomes MP4 de {file_path} : {e}")
    return False


def read_mp4_duration_seconds(file_path: str) -> float | None:
    """
    Lit la durée d'un MP4/M4V directement dans l'atome 'mvhd' (imbriqué dans
    'moov'), sans ffprobe — repli utilisé quand ffprobe est indisponible (réf.
    Lot 8, docs/plan-implementation-android.md : aucun binaire utilisable sous
    Android) pour au moins récupérer la durée, seule métadonnée manquante
    qu'un parcours d'en-têtes pur Python peut raisonnablement reconstituer
    (largeur/hauteur/codec demanderaient de décoder les box 'stsd', bien plus
    engagé pour un gain d'affichage secondaire).

    Même style de parcours que is_faststart_mp4 ci-dessus (en-têtes de boîtes
    uniquement) : d'abord les boîtes top-level jusqu'à 'moov', puis un second
    parcours, imbriqué, à l'intérieur de son contenu jusqu'à 'mvhd'. Renvoie
    None si le fichier n'a pas cette structure (pas un vrai MP4/M4V) ou en cas
    d'erreur de lecture — jamais d'exception, un appelant traite déjà une
    durée manquante comme telle.
    """
    try:
        with open(file_path, "rb") as f:
            file_size = os.fstat(f.fileno()).st_size

            def find_child_box(start: int, end: int, target: bytes) -> tuple[int, int] | None:
                """Cherche `target` parmi les boîtes enfants directes de
                l'intervalle [start, end) ; renvoie (offset_contenu, taille_contenu)."""
                pos = start
                while pos < end:
                    f.seek(pos)
                    header = f.read(8)
                    if len(header) < 8:
                        return None
                    size = int.from_bytes(header[0:4], "big")
                    box_type = header[4:8]
                    header_len = 8
                    if size == 1:
                        ext = f.read(8)
                        if len(ext) < 8:
                            return None
                        size = int.from_bytes(ext, "big")
                        header_len = 16
                    elif size == 0:
                        size = end - pos
                    if size < header_len:
                        return None
                    if box_type == target:
                        return pos + header_len, size - header_len
                    pos += size
                return None

            moov = find_child_box(0, file_size, b"moov")
            if moov is None:
                return None
            moov_start, moov_size = moov

            mvhd = find_child_box(moov_start, moov_start + moov_size, b"mvhd")
            if mvhd is None:
                return None
            mvhd_start, _ = mvhd

            f.seek(mvhd_start)
            version_flags = f.read(4)
            if len(version_flags) < 4:
                return None
            version = version_flags[0]
            if version == 1:
                f.seek(mvhd_start + 4 + 16)
                rest = f.read(12)
                if len(rest) < 12:
                    return None
                timescale = int.from_bytes(rest[0:4], "big")
                duration = int.from_bytes(rest[4:12], "big")
            else:
                f.seek(mvhd_start + 4 + 8)
                rest = f.read(8)
                if len(rest) < 8:
                    return None
                timescale = int.from_bytes(rest[0:4], "big")
                duration = int.from_bytes(rest[4:8], "big")

            if not timescale:
                return None
            return duration / timescale
    except OSError as e:
        logger.warning(f"Impossible de lire la durée MP4 (mvhd) de {file_path} : {e}")
        return None


def check_compatibility(metadata: dict, file_path: str, strict_video_codec: bool = False) -> dict:
    """
    Vérifie la compatibilité de la vidéo par rapport aux règles de lecture directe du navigateur.
    Retourne si le fichier est directement lisible ou s'il nécessite une normalisation.

    `strict_video_codec` (réf. audit plan-corrections-bugs, point 6) : à
    activer uniquement pour les fonds animés, qui bouclent indéfiniment et
    sollicitent donc le décodeur matériel bien plus durement (redémarrage à
    chaque tour) qu'une vidéo de cours lue une seule fois en continu. Pour un
    cours (False), la liste blanche reste appliquée mais élargie à HEVC/VP9
    (COMPATIBLE_COURSE_VIDEO_CODECS) plutôt que d'être ignorée : un codec
    jamais validé sur ce matériel déclenche quand même un réencodage.
    """
    if metadata["is_drm"]:
        return {
            "is_compatible": False,
            "needs_normalization": False,
            "actions": [],
            "error": "Le fichier vidéo est protégé par DRM (FairPlay, etc.) et ne peut pas être lu."
        }

    ext = Path(file_path).suffix.lower()
    is_mp4_container = ext in (".mp4", ".m4v")
    is_audio_compatible = metadata["audio_codec"] is None or metadata["audio_codec"] == "aac"
    # Un flux vidéo absent (audio seul) n'a rien à réencoder ; sinon le codec
    # doit être dans la liste blanche correspondante (stricte pour un fond
    # animé, élargie HEVC/VP9 pour un cours — jamais totalement ignorée).
    allowed_video_codecs = COMPATIBLE_VIDEO_CODECS if strict_video_codec else COMPATIBLE_COURSE_VIDEO_CODECS
    is_video_codec_compatible = metadata["codec"] is None or metadata["codec"] in allowed_video_codecs

    needs_audio_recode = metadata["audio_codec"] is not None and metadata["audio_codec"] != "aac"
    needs_container_recode = not is_mp4_container
    needs_video_recode = not is_video_codec_compatible
    # Réf. correctif "critique kiosk/réseau — reste figé sur la première
    # frame" : un conteneur/codec par ailleurs déjà compatible peut quand même
    # avoir son atome moov en fin de fichier (export non "web optimisé") — un
    # défaut invisible en local mais bloquant sur le réseau. Seul un
    # conteneur MP4 est concerné (un remux container->mp4 ci-dessous produit
    # déjà du faststart via normalize_video).
    needs_faststart_remux = (
        is_mp4_container and metadata.get("codec") is not None and not is_faststart_mp4(file_path)
    )

    actions = []
    if needs_video_recode:
        actions.append("recode_video")
    if needs_audio_recode:
        actions.append("recode_audio")
    if needs_container_recode:
        actions.append("recode_container")
    if needs_faststart_remux and not needs_container_recode:
        actions.append("remux_faststart")

    is_compatible = is_mp4_container and is_audio_compatible and is_video_codec_compatible

    return {
        "is_compatible": is_compatible,
        "needs_normalization": len(actions) > 0,
        "actions": actions,
        "error": None
    }


def generate_thumbnail(video_path: str, thumbnail_dir: str, duration: float | None) -> str:
    """
    Génère une miniature à 10% du début de la vidéo à l'aide de ffmpeg.
    """
    # Calcul de l'offset temporel (10% de la durée, minimum 1.0s, défaut 5.0s)
    offset = 5.0
    if duration:
        offset = max(1.0, duration * 0.1)

    # Si la vidéo est trop courte, on réduit l'offset initial
    if duration and offset >= duration:
        offset = duration * 0.1

    thumb_filename = f"thumb_{uuid.uuid4().hex}.jpg"
    thumb_path = Path(thumbnail_dir) / thumb_filename

    # S'assurer que le dossier de destination existe
    thumb_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        FFMPEG_BIN,
        "-ss", str(offset),
        "-i", video_path,
        "-vframes", "1",
        "-q:v", "2",  # Qualité (1-31, 1 est le meilleur, 2 est quasi sans perte)
        "-strict", "-2",  # Allow unofficial limited-range YUV for mjpeg encoder (needed for FFmpeg 8.0+)
        "-update", "1",   # Prevent single-frame warning/error on output file name
        "-y",
        str(thumb_path)
    ]

    from app.utils.deployment import get_deployment_profile
    is_android = get_deployment_profile() == "android"

    def _try_run_thumb(current_cmd: list[str]) -> bool:
        try:
            subprocess.run(current_cmd, capture_output=True, text=True, check=True, timeout=FFMPEG_THUMBNAIL_TIMEOUT_SECONDS)
            if thumb_path.exists() and thumb_path.stat().st_size > 0:
                return True
        except subprocess.CalledProcessError as err:
            if is_android and ("av1" in (err.stderr or "").lower() or "not implemented" in (err.stderr or "").lower()):
                # Tentative avec le décodeur matériel MediaCodec
                cmd_retry = [FFMPEG_BIN, "-operating_rate", "1000", "-c:v", "av1_mediacodec"] + current_cmd[1:]
                try:
                    subprocess.run(cmd_retry, capture_output=True, text=True, check=True, timeout=FFMPEG_THUMBNAIL_TIMEOUT_SECONDS)
                    if thumb_path.exists() and thumb_path.stat().st_size > 0:
                        return True
                except Exception as e_ret:
                    logger.error(f"ffmpeg thumbnail retry av1_mediacodec failed: {e_ret}")
            logger.error(f"ffmpeg thumbnail attempt failed: {err.stderr}")
        return False

    if _try_run_thumb(cmd):
        return str(thumb_path)

    # Premier fallback : offset à 0.1s
    if offset != 0.1:
        new_offset = 0.1
        if duration and new_offset >= duration:
            new_offset = 0.0
        cmd[2] = str(new_offset)
        if _try_run_thumb(cmd):
            return str(thumb_path)

    # Deuxième fallback : début absolu (0.0s)
    cmd[2] = "0.0"
    if _try_run_thumb(cmd):
        return str(thumb_path)

    raise ValueError("Impossible de générer la miniature avec ffmpeg : le fichier de sortie est vide ou inexistant.")


def _get_target_bitrate(width: int | None, height: int | None) -> str:
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


def _get_encoder_args(is_android: bool, width: int | None, height: int | None) -> tuple[list[str], str]:
    """
    Détermine les arguments d'encodage optimaux selon la plateforme et le matériel détecté.
    Retourne (liste_arguments_ffmpeg, nom_encodeur).
    """
    bitrate = _get_target_bitrate(width, height)
    system = platform.system().lower()

    if is_android:
        # Qualcomm Snapdragon MediaCodec matériel : operating_rate 1000 pour horloge max,
        # nv12 pour zéro-copie avec le décodeur matériel.
        return (["-c:v", "h264_mediacodec", "-operating_rate", "1000", "-pix_fmt", "nv12", "-b:v", bitrate], "h264_mediacodec")

    if system == "darwin":
        # macOS : Apple Silicon (puces M1/M2/M3/M4) et Intel via VideoToolbox matériel
        return (["-c:v", "h264_videotoolbox", "-q:v", "65", "-pix_fmt", "yuv420p"], "h264_videotoolbox")

    if system == "linux":
        # Dell Wyse 5070 (Intel Gemini Lake UHD 600) ou station Linux avec VA-API QuickSync
        if os.path.exists("/dev/dri/renderD128") and os.access("/dev/dri/renderD128", os.R_OK | os.W_OK):
            return (["-vaapi_device", "/dev/dri/renderD128", "-vf", "format=nv12,hwupload", "-c:v", "h264_vaapi", "-b:v", bitrate], "h264_vaapi")

    # Repli logiciel universel haute compatibilité (Windows, serveurs headless sans GPU, repli après échec GPU)
    return (["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"], "libx264")


def _run_ffmpeg_with_progress(
    cmd: list[str],
    job_id: str | None,
    duration_seconds: float | None,
    timeout: int = FFMPEG_NORMALIZE_TIMEOUT_SECONDS,
) -> tuple[int, str]:
    """
    Exécute FFmpeg en sous-processus Popen avec télémétrie en direct (-progress pipe:1),
    enregistre le processus dans import_jobs pour permettre son annulation immédiate,
    et calcule en temps réel progress_percent, eta_seconds et speed.
    Retourne (returncode, stderr_output).
    """
    from app.utils.import_jobs import register_job_process, unregister_job_process, is_job_cancelled, update_job, JobCancelledError
    import threading

    if is_job_cancelled(job_id):
        raise JobCancelledError(f"Job {job_id} annulé avant le démarrage de FFmpeg")

    full_cmd = list(cmd)
    if "-progress" not in full_cmd:
        full_cmd.extend(["-progress", "pipe:1", "-nostats"])

    proc = subprocess.Popen(
        full_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    if job_id:
        register_job_process(job_id, proc)

    stderr_chunks: list[str] = []

    def _read_stderr():
        try:
            if proc.stderr:
                for s_line in proc.stderr:
                    stderr_chunks.append(s_line)
        except Exception:
            pass

    t_err = threading.Thread(target=_read_stderr, daemon=True)
    t_err.start()

    last_update = 0.0
    current_speed = None
    start_time = time.time()

    try:
        if proc.stdout:
            for line in proc.stdout:
                if is_job_cancelled(job_id):
                    proc.terminate()
                    try:
                        proc.wait(timeout=1.0)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                    raise JobCancelledError(f"Job {job_id} annulé par l'utilisateur")

                line = line.strip()
                if not line:
                    continue

                if line.startswith("speed="):
                    current_speed = line.split("=", 1)[1].strip()
                elif line.startswith("out_time_us="):
                    now = time.time()
                    # Mises à jour throttlées toutes les 500 ms maximum
                    if now - last_update >= 0.5:
                        last_update = now
                        try:
                            out_us = int(line.split("=", 1)[1].strip())
                            out_sec = out_us / 1_000_000.0
                            pct = None
                            eta = None
                            if duration_seconds and duration_seconds > 0:
                                pct = round(min(99.0, (out_sec / duration_seconds) * 100.0), 1)
                                if current_speed and current_speed.endswith("x"):
                                    try:
                                        spd_val = float(current_speed[:-1])
                                        if spd_val > 0.05:
                                            eta = max(0, int((duration_seconds - out_sec) / spd_val))
                                    except ValueError:
                                        pass
                            update_job(job_id, progress_percent=pct, eta_seconds=eta, speed=current_speed)
                        except Exception:
                            pass
                elif line == "progress=end":
                    update_job(job_id, progress_percent=100.0, eta_seconds=0)

        remaining_timeout = max(1.0, float(timeout - (time.time() - start_time)))
        proc.wait(timeout=remaining_timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        raise TimeoutError(f"Délai dépassé ({timeout}s) pour FFmpeg")
    finally:
        if job_id:
            unregister_job_process(job_id)
        t_err.join(timeout=1.0)

    stderr_text = "".join(stderr_chunks)
    if proc.returncode != 0:
        if is_job_cancelled(job_id):
            raise JobCancelledError(f"Job {job_id} annulé par l'utilisateur")
        return (proc.returncode, stderr_text)

    return (0, stderr_text)


def normalize_video(
    input_path: str,
    output_path: str,
    actions: list[str],
    source_metadata: dict | None = None,
    job_id: str | None = None,
) -> str:
    """
    Normalise le conteneur ou la piste audio/vidéo d'une vidéo de manière optimisée.
    - Stream copy quand les flux sont déjà compatibles (instantané).
    - Accélération matérielle multi-OS (Android Snapdragon MediaCodec, Apple Silicon VideoToolbox,
      Wyse/Linux Intel VA-API QuickSync) sans aucun downscale (conservation intégrale des résolutions 2K/4K).
    - Télémétrie en direct (ETA, pourcentage, vitesse) et interruption immédiate en cas d'annulation.
    """
    from app.utils.deployment import get_deployment_profile
    from app.utils.import_jobs import is_job_cancelled, JobCancelledError

    if is_job_cancelled(job_id):
        raise JobCancelledError(f"Job {job_id} annulé")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    meta = source_metadata if source_metadata is not None else extract_metadata(input_path)
    in_codec = (meta.get("codec") or "").lower()
    is_android = get_deployment_profile() == "android"

    def _build_cmd(enc_args: list[str], av1_hw_in: bool) -> list[str]:
        c = [FFMPEG_BIN]
        if is_android and av1_hw_in:
            c.extend(["-operating_rate", "1000", "-c:v", "av1_mediacodec"])
        c.extend(["-i", input_path])
        if "recode_video" in actions:
            c.extend(enc_args)
        else:
            c.extend(["-c:v", "copy"])

        has_audio = meta.get("audio_codec") is not None
        if not has_audio:
            c.append("-an")
        elif "recode_audio" in actions:
            c.extend(["-c:a", "aac"])
        else:
            c.extend(["-c:a", "copy"])

        c.extend(["-movflags", "+faststart", "-y", output_path])
        return c

    # 1. Sélection initiale de l'encodeur
    initial_enc_args, encoder_name = _get_encoder_args(is_android, meta.get("width"), meta.get("height"))
    use_av1_hw = is_android and (in_codec == "av1")
    cmd = _build_cmd(initial_enc_args, use_av1_hw)

    ret, stderr = _run_ffmpeg_with_progress(cmd, job_id, meta.get("duration_seconds"))
    if ret == 0:
        return output_path

    logger.warning(f"Échec de l'encodage avec {encoder_name} (code {ret}): {stderr}")

    # 2. Repli matériel VA-API ou VideoToolbox -> libx264 si échec GPU
    if encoder_name in ("h264_vaapi", "h264_videotoolbox"):
        logger.info(f"Repli vers l'encodeur logiciel libx264 suite à l'erreur {encoder_name}...")
        fallback_enc = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"]
        cmd_fallback = _build_cmd(fallback_enc, use_av1_hw)
        ret2, stderr2 = _run_ffmpeg_with_progress(cmd_fallback, job_id, meta.get("duration_seconds"))
        if ret2 == 0:
            return output_path
        stderr = stderr2

    # 3. Repli Android AV1 si le décodeur standard a échoué
    if is_android and not use_av1_hw and ("av1" in stderr.lower() or "not implemented" in stderr.lower()):
        logger.info("Détection d'un flux AV1 non géré par le décodeur par défaut, bascule vers av1_mediacodec...")
        cmd_av1 = _build_cmd(initial_enc_args, av1_hw_in=True)
        ret3, stderr3 = _run_ffmpeg_with_progress(cmd_av1, job_id, meta.get("duration_seconds"))
        if ret3 == 0:
            return output_path
        stderr = stderr3

    raise ValueError(f"Échec de la normalisation de la vidéo avec ffmpeg : {stderr}")

