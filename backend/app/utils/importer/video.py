"""Import d'une vidéo de cours."""
import os
import uuid
import shutil
import logging
from pathlib import Path
from app.config import settings
from app.database import SessionLocal
from app.models import Video, ImportSource
from app.utils.activity_log import log_activity
from app.utils.video_utils.compatibility import check_compatibility
from app.utils.video_utils.thumbnails import generate_thumbnail
from app.utils.video_utils.normalize import normalize_video, estimate_normalize_seconds
from app.utils.import_jobs import update_job, is_job_cancelled, JobCancelledError
from app.utils.importer.metadata import extract_metadata_or_unknown
from app.utils.importer.naming import parse_title_program_release
from app.utils.importer.staging import wait_for_file_to_copy


logger = logging.getLogger(__name__)


def import_video(src_path: str, original_filename: str, source: ImportSource, job_id: str | None = None) -> Video:
    """
    Gère le flux complet d'importation d'une vidéo :
    1. Attente de la stabilisation du fichier.
    2. Extraction des métadonnées et vérification des DRM.
    3. Déplacement/Normalisation du fichier dans le répertoire média final.
    4. Génération de la miniature.
    5. Insertion en base de données.

    `job_id` : identifiant
    optionnel d'une tâche déjà enregistrée via `app.utils.import_jobs`, mis à
    jour à chaque étape pour que l'UI d'admin affiche une progression réelle
    plutôt qu'un indicateur "en cours" muet. `None` (défaut) laisse la
    fonction utilisable telle quelle sans file à suivre (tests, appels
    existants).
    """
    path_obj = Path(src_path)

    # 1. Attendre la stabilisation du fichier (si c'est un fichier local / watcher)
    if source == ImportSource.watched_folder:
        if not wait_for_file_to_copy(src_path):
            raise TimeoutError(f"Le fichier {original_filename} ne s'est pas stabilisé dans le temps imparti.")

    # 2. Extraction des métadonnées
    update_job(job_id, stage="probing")
    meta = extract_metadata_or_unknown(src_path, original_filename)

    if meta["is_drm"]:
        # Suppression du fichier source en cas de DRM pour éviter des boucles infinies ou encombrements
        if path_obj.exists():
            try:
                os.remove(src_path)
            except Exception as e:
                logger.error(f"Impossible de supprimer le fichier DRM {src_path}: {e}")
        raise ValueError(
            f"Le fichier {original_filename} est protégé par DRM et ne peut pas être lu."
        )

    # Vérification de la compatibilité
    compat = check_compatibility(meta, src_path)

    file_id = uuid.uuid4().hex
    clean_name = "".join(c for c in original_filename if c.isalnum() or c in (".", "_", "-")).strip()

    # Définition des dossiers
    Path(settings.media_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.thumbnails_dir).mkdir(parents=True, exist_ok=True)

    dest_path = None
    thumbnail_path = None

    try:
        if is_job_cancelled(job_id):
            raise JobCancelledError(f"Job {job_id} annulé")

        if compat["needs_normalization"]:
            # Estimation initiale : affichée le temps que ffmpeg
            # démarre et émette sa propre progression en direct, qui prend
            # ensuite le relais (cf. run_ffmpeg_with_progress).
            update_job(job_id, stage="normalizing", estimated_seconds=estimate_normalize_seconds(meta))
            # Déplacement vers un fichier temporaire pour normalisation
            temp_filename = f"temp_{file_id}_{clean_name}"
            temp_dest_path = Path(settings.media_dir) / temp_filename

            logger.info(f"Déplacement de {src_path} vers {temp_dest_path} pour normalisation")
            shutil.move(src_path, temp_dest_path)

            # Le fichier normalisé sera temporaire d'abord, puis déplacé vers son nom final
            temp_norm_dest_path = Path(settings.media_dir) / f"temp_norm_{file_id}_{Path(clean_name).stem}.mp4"
            final_filename = f"video_{file_id}_{Path(clean_name).stem}.mp4"
            final_dest_path = Path(settings.media_dir) / final_filename

            logger.info(f"Normalisation de {temp_dest_path} vers {final_dest_path} via actions: {compat['actions']}")
            try:
                normalize_video(str(temp_dest_path), str(temp_norm_dest_path), compat["actions"], source_metadata=meta, job_id=job_id)
                if temp_norm_dest_path.exists():
                    shutil.move(temp_norm_dest_path, final_dest_path)
                dest_path = final_dest_path
                # Extraire à nouveau les métadonnées sur le fichier normalisé final
                meta = extract_metadata_or_unknown(str(dest_path), original_filename)
            finally:
                if temp_dest_path.exists():
                    os.remove(temp_dest_path)
                if temp_norm_dest_path.exists():
                    os.remove(temp_norm_dest_path)
        else:
            update_job(job_id, stage="copying")
            # Fichier compatible : déplacement direct vers le dossier de destination
            dest_filename = f"video_{file_id}_{clean_name}"
            dest_path = Path(settings.media_dir) / dest_filename
            logger.info(f"Déplacement direct de {src_path} vers {dest_path}")
            shutil.move(src_path, dest_path)

        if is_job_cancelled(job_id):
            raise JobCancelledError(f"Job {job_id} annulé")

        # 3. Génération de la miniature
        update_job(job_id, stage="thumbnail")
        try:
            thumbnail_path = generate_thumbnail(
                str(dest_path), settings.thumbnails_dir, meta["duration_seconds"]
            )
        except Exception as te:
            logger.error(f"Échec de la génération de miniature pour {dest_path}: {te}")
            thumbnail_path = None

        if is_job_cancelled(job_id):
            raise JobCancelledError(f"Job {job_id} annulé")

        # 4. Enregistrement en base de données
        update_job(job_id, stage="saving")
        db = SessionLocal()
        try:
            # Titre propre, programme et release déduits du nom du fichier
            title, program, release = parse_title_program_release(original_filename)

            video = Video(
                file_path=str(dest_path),
                title=title,
                program=program,
                release=release,
                duration_seconds=meta.get("duration_seconds"),
                width=meta.get("width"),
                height=meta.get("height"),
                codec=meta.get("codec"),
                thumbnail_path=thumbnail_path,
                source=source,
                description=meta.get("description"),
                audio_channels=meta.get("audio_channels"),
                audio_codec=meta.get("audio_codec"),
                fps=meta.get("fps"),
                bitrate_kbps=meta.get("bitrate_kbps"),
                pix_fmt=meta.get("pix_fmt"),
            )
            db.add(video)
            db.commit()
            db.refresh(video)
            logger.info(f"Vidéo indexée avec succès dans la base : {video.title} (ID: {video.id})")
            # log_activity() fait son propre commit sur la même session, ce
            # qui réexpire les attributs déjà chargés de `video` (comportement
            # par défaut de SQLAlchemy) — un second refresh() est nécessaire
            # après, pendant que la session est encore ouverte, sinon le
            # premier accès à un attribut par l'appelant (après la fermeture
            # de la session) lève DetachedInstanceError.
            log_activity(
                db, "video_imported",
                f"{video.title} ({'téléversement' if source == ImportSource.upload else 'dossier surveillé'})",
            )
            db.refresh(video)
            return video
        except Exception as dbe:
            db.rollback()
            logger.error(f"Erreur DB lors de l'enregistrement de {original_filename}: {dbe}")
            # Nettoyer les fichiers créés
            if dest_path and dest_path.exists():
                os.remove(dest_path)
            if thumbnail_path and Path(thumbnail_path).exists():
                os.remove(thumbnail_path)
            raise dbe
        finally:
            db.close()

    except JobCancelledError:
        logger.info(f"Import {job_id} annulé par l'utilisateur : nettoyage des fichiers partiels...")
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
        logger.error(f"Erreur lors de l'importation de {original_filename}: {e}")
        # S'assurer que le fichier source est nettoyé s'il s'agissait du watcher
        if source == ImportSource.watched_folder and path_obj.exists():
            try:
                os.remove(src_path)
            except Exception:
                pass
        raise e
