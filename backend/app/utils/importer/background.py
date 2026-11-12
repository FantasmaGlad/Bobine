"""Import d'un fond (vidéo ou image)."""
import os
import uuid
import shutil
import logging
from pathlib import Path
from app.config import settings
from app.database import SessionLocal
from app.models import Background, ImportSource
from app.utils.activity_log import log_activity
from app.utils.video_utils.compatibility import check_compatibility
from app.utils.video_utils.thumbnails import generate_placeholder_thumbnail, generate_thumbnail
from app.utils.video_utils.normalize import normalize_video, estimate_normalize_seconds
from app.utils.import_jobs import update_job, is_job_cancelled, JobCancelledError
from app.utils.importer.formats import IMAGE_EXTENSIONS
from app.utils.importer.metadata import extract_metadata_or_unknown
from app.utils.importer.staging import wait_for_file_to_copy


logger = logging.getLogger(__name__)


def import_background_image(src_path: str, original_filename: str, job_id: str | None = None) -> Background:
    """Fond fixe : pipeline dédié, sans ffmpeg — une image n'a ni codec à valider ni normalisation à envisager, seule sa décodabilité compte (via Pillow)."""
    from PIL import Image, UnidentifiedImageError

    update_job(job_id, stage="probing")
    Path(settings.backgrounds_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.thumbnails_dir).mkdir(parents=True, exist_ok=True)

    try:
        with Image.open(src_path) as img:
            img.verify()
    except (UnidentifiedImageError, OSError) as e:
        raise ValueError(f"Le fichier {original_filename} n'est pas une image valide : {e}")

    file_id = uuid.uuid4().hex
    ext = Path(original_filename).suffix.lower()
    dest_path = Path(settings.backgrounds_dir) / f"bg_{file_id}{ext}"
    shutil.move(src_path, dest_path)

    update_job(job_id, stage="thumbnail")
    thumbnail_path = None
    try:
        with Image.open(dest_path) as img:
            img = img.convert("RGB")
            img.thumbnail((1920, 1080), Image.Resampling.LANCZOS)
            thumb_dest = Path(settings.thumbnails_dir) / f"thumb_{file_id}.jpg"
            img.save(thumb_dest, "JPEG", quality=92, optimize=True)
            thumbnail_path = str(thumb_dest)
    except Exception as te:
        logger.error(f"Échec de la génération de miniature pour {dest_path}: {te}")
        try:
            thumbnail_path = generate_placeholder_thumbnail(settings.thumbnails_dir, Path(original_filename).stem)
        except Exception as pe:
            logger.error(f"Miniature de secours impossible pour {dest_path}: {pe}")

    update_job(job_id, stage="saving")
    db = SessionLocal()
    try:
        title = Path(original_filename).stem.replace("_", " ").replace("-", " ")
        background = Background(
            file_path=str(dest_path),
            title=title,
            duration_seconds=None,
            thumbnail_path=thumbnail_path,
        )
        db.add(background)
        db.commit()
        db.refresh(background)
        logger.info(f"Fond animé (image) indexé avec succès : {background.title} (ID: {background.id})")
        log_activity(db, "background_imported", background.title)
        db.refresh(background)
        return background
    except Exception as dbe:
        db.rollback()
        logger.error(f"Erreur DB lors de l'enregistrement du fond {original_filename}: {dbe}")
        if dest_path.exists():
            os.remove(dest_path)
        if thumbnail_path and Path(thumbnail_path).exists():
            os.remove(thumbnail_path)
        raise dbe
    finally:
        db.close()


def import_background(
    src_path: str, original_filename: str, source: ImportSource, job_id: str | None = None
) -> Background:
    """Importe un fond animé : même pipeline que import_video (stabilisation, métadonnées, normalisation si nécessaire, miniature) mais dans le dossier dédié `settings.backgrounds_dir`, sans parsing programme/ release (non pertinent pour une boucle d'ambiance) et sans piste audio (les fonds animés sont toujours joués sans son)."""
    path_obj = Path(src_path)

    if source == ImportSource.watched_folder:
        if not wait_for_file_to_copy(src_path):
            raise TimeoutError(f"Le fichier {original_filename} ne s'est pas stabilisé dans le temps imparti.")

    if path_obj.suffix.lower() in IMAGE_EXTENSIONS:
        return import_background_image(src_path, original_filename, job_id=job_id)

    update_job(job_id, stage="probing")
    meta = extract_metadata_or_unknown(src_path, original_filename)

    if meta["is_drm"]:
        if path_obj.exists():
            try:
                os.remove(src_path)
            except Exception as e:
                logger.error(f"Impossible de supprimer le fichier DRM {src_path}: {e}")
        raise ValueError(
            f"Le fichier {original_filename} est protégé par DRM et ne peut pas être lu."
        )

    compat = check_compatibility(meta, src_path, strict_video_codec=True)

    file_id = uuid.uuid4().hex
    clean_name = "".join(c for c in original_filename if c.isalnum() or c in (".", "_", "-")).strip()

    Path(settings.backgrounds_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.thumbnails_dir).mkdir(parents=True, exist_ok=True)

    dest_path = None
    thumbnail_path = None

    try:
        if is_job_cancelled(job_id):
            raise JobCancelledError(f"Job {job_id} annulé")

        if compat["needs_normalization"]:
            update_job(job_id, stage="normalizing", estimated_seconds=estimate_normalize_seconds(meta))
            temp_filename = f"temp_{file_id}_{clean_name}"
            temp_dest_path = Path(settings.backgrounds_dir) / temp_filename
            shutil.move(src_path, temp_dest_path)

            temp_norm_dest_path = Path(settings.backgrounds_dir) / f"temp_norm_{file_id}_{Path(clean_name).stem}.mp4"
            final_filename = f"bg_{file_id}_{Path(clean_name).stem}.mp4"
            final_dest_path = Path(settings.backgrounds_dir) / final_filename

            try:
                normalize_video(str(temp_dest_path), str(temp_norm_dest_path), compat["actions"], source_metadata=meta, job_id=job_id)
                if temp_norm_dest_path.exists():
                    shutil.move(temp_norm_dest_path, final_dest_path)
                dest_path = final_dest_path
                meta = extract_metadata_or_unknown(str(dest_path), original_filename)
            finally:
                if temp_dest_path.exists():
                    os.remove(temp_dest_path)
                if temp_norm_dest_path.exists():
                    os.remove(temp_norm_dest_path)
        else:
            update_job(job_id, stage="copying")
            dest_filename = f"bg_{file_id}_{clean_name}"
            dest_path = Path(settings.backgrounds_dir) / dest_filename
            shutil.move(src_path, dest_path)

        if is_job_cancelled(job_id):
            raise JobCancelledError(f"Job {job_id} annulé")

        update_job(job_id, stage="thumbnail")
        try:
            thumbnail_path = generate_thumbnail(
                str(dest_path), settings.thumbnails_dir, meta["duration_seconds"]
            )
        except Exception as te:
            logger.error(f"Échec de la génération de miniature pour {dest_path}: {te}")
            try:
                thumbnail_path = generate_placeholder_thumbnail(
                    settings.thumbnails_dir, Path(original_filename).stem
                )
            except Exception as pe:
                logger.error(f"Miniature de secours impossible pour {dest_path}: {pe}")
                thumbnail_path = None

        if is_job_cancelled(job_id):
            raise JobCancelledError(f"Job {job_id} annulé")

        update_job(job_id, stage="saving")
        db = SessionLocal()
        try:
            title = Path(original_filename).stem.replace("_", " ").replace("-", " ")
            background = Background(
                file_path=str(dest_path),
                title=title,
                duration_seconds=meta["duration_seconds"],
                thumbnail_path=thumbnail_path,
            )
            db.add(background)
            db.commit()
            db.refresh(background)
            logger.info(f"Fond animé indexé avec succès : {background.title} (ID: {background.id})")
            log_activity(db, "background_imported", background.title)
            db.refresh(background)
            return background
        except Exception as dbe:
            db.rollback()
            logger.error(f"Erreur DB lors de l'enregistrement du fond {original_filename}: {dbe}")
            if dest_path and dest_path.exists():
                os.remove(dest_path)
            if thumbnail_path and Path(thumbnail_path).exists():
                os.remove(thumbnail_path)
            raise dbe
        finally:
            db.close()

    except JobCancelledError:
        logger.info(f"Fond animé {job_id} annulé par l'utilisateur : nettoyage des fichiers partiels...")
        if dest_path and Path(dest_path).exists():
            try:
                os.remove(dest_path)
            except Exception:
                pass
        if thumbnail_path and Path(thumbnail_path).exists():
            try:
                os.remove(thumbnail_path)
            except Exception:
                pass
        raise

    except Exception as e:
        logger.error(f"Erreur lors de l'importation du fond animé {original_filename}: {e}")
        if source == ImportSource.watched_folder and path_obj.exists():
            try:
                os.remove(src_path)
            except Exception:
                pass
        raise e
