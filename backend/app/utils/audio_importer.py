import os
import re
import time
import uuid
import shutil
import logging
import tempfile
from pathlib import Path

from app.utils import media_formats
from app.config import settings
from app.database import SessionLocal
from app.models import AudioCourse, AudioTrack
from app.utils.activity_log import log_activity
from app.utils.audio_utils import parse_track_number_and_title
from app.utils.media_metadata import extract_audio_duration
from app.utils.import_jobs import update_job
from app.utils.zip_safety import InvalidArchiveError, UnsafeZipError, safe_extract_archive

logger = logging.getLogger(__name__)

AUDIO_EXTENSIONS = media_formats.COURSE_AUDIO


def _guess_program(title: str) -> str | None:
    upper = title.upper()
    if "RPM" in upper:
        return "RPM"
    if "SPRINT" in upper:
        return "Sprint"
    if "TRIP" in upper:
        return "The Trip"
    return None


_RESOLUTION_NUMBERS = {"144", "240", "360", "480", "720", "1080", "1440", "2160", "4320"}


def _guess_release(title: str) -> str | None:
    for word, number in re.findall(r"([A-Za-zÀ-ÖØ-öø-ÿ]+)[\s_-]+(\d{1,4})\b", title):
        is_year = len(number) == 4 and 1900 <= int(number) <= 2099
        if is_year or number in _RESOLUTION_NUMBERS:
            continue
        return number
    return None


def wait_for_folder_to_stabilize(dir_path: str, stable_secs: int = 3, timeout: int = 300) -> bool:
    """Variante de `importer.wait_for_file_to_copy` pour un dossier entier."""
    last_total = -1
    stable_since = 0
    start_time = time.time()

    while time.time() - start_time < timeout:
        path = Path(dir_path)
        if not path.exists():
            time.sleep(0.5)
            continue

        try:
            files = [p for p in path.iterdir() if p.is_file() and not p.name.startswith(".")]
            total = sum(p.stat().st_size for p in files)
        except OSError:
            time.sleep(0.5)
            continue

        if total == last_total and total > 0 and files:
            stable_since += 1
            if stable_since >= stable_secs:
                return True
        else:
            last_total = total
            stable_since = 0

        time.sleep(1)

    return False


def import_audio_course_from_files(
    mp3_paths: list[str],
    course_title: str,
    program: str | None = None,
    release: str | None = None,
    job_id: str | None = None,
) -> AudioCourse:
    """Importe un cours audio à partir d'une liste de fichiers MP3 déjà présents sur disque."""
    if not mp3_paths:
        raise ValueError("Aucun fichier MP3 fourni pour l'import du cours audio.")

    update_job(job_id, stage="probing")
    course_dir = Path(settings.audio_dir) / f"course_{uuid.uuid4().hex}"
    course_dir.mkdir(parents=True, exist_ok=True)

    parsed = []
    for src in mp3_paths:
        src_path = Path(src)
        number, title = parse_track_number_and_title(src_path.name)
        parsed.append((number, title, src_path))

    parsed.sort(key=lambda t: (t[0] is None, t[0] if t[0] is not None else 0, str(t[2])))

    update_job(job_id, stage="saving")
    db = SessionLocal()
    try:
        course = AudioCourse(
            title=course_title,
            program=program if program else _guess_program(course_title),
            release=release if release else _guess_release(course_title),
        )
        db.add(course)
        db.flush()

        for position, (number, title, src_path) in enumerate(parsed):
            duration = extract_audio_duration(str(src_path))
            dest_name = f"track_{uuid.uuid4().hex}{src_path.suffix.lower()}"
            dest_path = course_dir / dest_name
            shutil.move(str(src_path), dest_path)

            track = AudioTrack(
                audio_course_id=course.id,
                number=number,
                title=title or f"Piste {position + 1}",
                file_path=str(dest_path),
                duration_seconds=duration,
                position=position,
            )
            db.add(track)

        db.commit()
        db.refresh(course)
        logger.info(f"Cours audio importé : {course.title} ({len(parsed)} piste(s), ID {course.id})")
        log_activity(db, "audio_course_imported", f"{course.title} ({len(parsed)} piste(s))")
        _ = list(course.tracks)
        return course
    except Exception as e:
        db.rollback()
        if course_dir.exists():
            shutil.rmtree(course_dir, ignore_errors=True)
        logger.error(f"Erreur lors de l'import du cours audio {course_title}: {e}")
        raise e
    finally:
        db.close()


def import_audio_course_from_zip(
    zip_path: str,
    course_title: str,
    program: str | None = None,
    release: str | None = None,
    job_id: str | None = None,
) -> AudioCourse:
    """Extrait une archive ZIP d'un cours complet puis importe les MP3 qu'elle contient."""
    update_job(job_id, stage="extracting")
    with tempfile.TemporaryDirectory() as tmp_dir:
        try:
            safe_extract_archive(Path(zip_path), Path(tmp_dir))
        except InvalidArchiveError:
            raise
        except UnsafeZipError as e:
            raise ValueError(str(e))
        finally:
            if Path(zip_path).exists():
                os.remove(zip_path)

        mp3_paths = sorted(
            str(p) for p in Path(tmp_dir).rglob("*")
            if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS and not p.name.startswith(".")
        )
        if not mp3_paths:
            raise ValueError("Aucun fichier MP3 trouvé dans l'archive ZIP.")

        return import_audio_course_from_files(mp3_paths, course_title, program, release, job_id=job_id)


def import_audio_course_from_watched_folder(course_dir: str, job_id: str | None = None) -> AudioCourse:
    """Importe un cours audio détecté par le watcher : le nom du sous-dossier devient le titre du cours, tous les MP3 qu'il contient (à plat, non récursif) en deviennent les pistes."""
    path = Path(course_dir)
    course_title = path.name.replace("_", " ").replace("-", " ").strip() or "Cours importé"

    mp3_paths = sorted(
        str(p) for p in path.iterdir()
        if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS and not p.name.startswith(".")
    )
    if not mp3_paths:
        raise ValueError(f"Le dossier {path.name} ne contient aucun fichier MP3.")

    course = import_audio_course_from_files(mp3_paths, course_title, job_id=job_id)

    try:
        shutil.rmtree(path, ignore_errors=True)
    except Exception:
        pass

    return course
