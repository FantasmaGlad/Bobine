import os
import uuid
import shutil
import logging
import tempfile
from pathlib import Path
from typing import List

from fastapi import (
    APIRouter,
    Depends,
    UploadFile,
    File,
    Form,
    HTTPException,
)
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal
from app.models import Video, VideoSubtitle, ImportSource
from app.config import settings
from app.utils.subtitles import (
    convert_srt_to_vtt,
    detect_language_from_filename,
    get_subtitles_directory,
    LANGUAGE_MAP,
)
from app.utils.importer import import_video
from app.utils.executors import ffmpeg_executor
from app.utils.staged_uploads import receive_single_upload
from app.utils.web_rendition import remove_web_file, request_web_rendition
from app.utils.import_jobs import create_job, update_job, register_job_future, JobCancelledError
from app.utils.ws_manager import manager as ws_manager
from app.utils.video_utils import (
    extract_metadata,
    check_compatibility,
    normalize_video,
    generate_thumbnail,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/videos", tags=["videos"])


class VideoUpdate(BaseModel):
    title: str | None = None
    program: str | None = None
    release: str | None = None
    description: str | None = None


class VideoResponse(BaseModel):
    id: int
    file_path: str
    title: str
    program: str | None
    release: str | None
    duration_seconds: float | None
    width: int | None
    height: int | None
    codec: str | None
    thumbnail_path: str | None
    source: str
    description: str | None = None
    audio_channels: int | None = None
    audio_codec: str | None = None
    fps: float | None = None
    bitrate_kbps: int | None = None
    pix_fmt: str | None = None
    # Lisibilité sur les navigateurs tiers (cf. app/utils/web_profile.py) :
    # `web_issues` vide = lisible partout ; `web_status` = état de la version web.
    web_safe: bool = True
    web_issues: List[str] = []
    web_status: str | None = None

    class Config:
        from_attributes = True
        orm_mode = True  # Pydantic v1 (profil Android, cf. docs/ARCHITECTURE.md §3.1) - v2 ignore silencieusement cette cle inconnue


class VideoSubtitleResponse(BaseModel):
    id: int
    video_id: int
    language_code: str
    language_label: str
    format: str
    vtt_url: str

    class Config:
        from_attributes = True
        orm_mode = True


class ImportJobAccepted(BaseModel):
    job_id: str


def _run_video_import_job(
    job_id: str,
    temp_path: str,
    filename: str,
    title: str | None,
    program: str | None,
    release: str | None,
    description: str | None = None,
    subtitle_temps: list[tuple[str, str]] | None = None,
) -> None:
    """
    Exécutée sur `ffmpeg_executor`.
    Contrairement à l'ancienne implémentation synchrone, la requête HTTP
    d'upload ne bloque plus jusqu'à la fin de cette fonction (qui peut
    prendre jusqu'à FFMPEG_NORMALIZE_TIMEOUT_SECONDS = 30 min) — elle est
    seulement mise en file, et son avancement est visible via
    `app.utils.import_jobs` / `GET /api/import-jobs`.
    """
    try:
        video = import_video(temp_path, filename, ImportSource.upload, job_id=job_id)

        db = SessionLocal()
        try:
            db_video = db.query(Video).filter(Video.id == video.id).first()
            if db_video:
                if title:
                    db_video.title = title
                if program:
                    db_video.program = program
                if release:
                    db_video.release = release
                if description:
                    db_video.description = description
                db.commit()
                result_id = db_video.id

                # Traiter les sous-titres joints à l'import si fournis
                if subtitle_temps:
                    subtitles_dir = get_subtitles_directory()
                    for sub_temp_path, sub_orig_name in subtitle_temps:
                        try:
                            lang_code, lang_label = detect_language_from_filename(sub_orig_name)
                            raw_content = Path(sub_temp_path).read_text(encoding="utf-8", errors="replace")
                            is_vtt = sub_orig_name.lower().endswith(".vtt") or raw_content.lstrip().startswith("WEBVTT")
                            vtt_content = raw_content if is_vtt else convert_srt_to_vtt(raw_content)
                            out_filename = f"{result_id}_{lang_code}_{uuid.uuid4().hex[:8]}.vtt"
                            out_path = subtitles_dir / out_filename
                            out_path.write_text(vtt_content, encoding="utf-8")
                            sub = VideoSubtitle(
                                video_id=result_id,
                                language_code=lang_code,
                                language_label=lang_label,
                                file_path=str(out_path.resolve()),
                                format="vtt",
                            )
                            db.add(sub)
                            db.commit()
                        except Exception as sub_err:
                            logger.warning("Erreur import sous-titre joint %s pour video %s : %s", sub_orig_name, result_id, sub_err)
            else:
                result_id = video.id
        finally:
            db.close()

        # Notification WebSocket : un
        # cours importé doit apparaître SANS délai sur /grid, /cinema et
        # /library déjà ouverts, pas seulement au prochain sondage (15s
        # sur /grid et /cinema, jamais sur /library). Exécuté hors boucle
        # asyncio (thread de ffmpeg_executor) — version thread-safe.
        ws_manager.broadcast_threadsafe({"event": "library_change", "reason": "video_imported"})
        update_job(job_id, stage="done", result_id=result_id)
    except JobCancelledError:
        logger.info(f"Tâche d'import vidéo {job_id} annulée.")
        update_job(job_id, stage="cancelled")
    except Exception as e:
        logger.error(f"Erreur lors de l'upload et de l'import de la vidéo (job {job_id}): {e}", exc_info=True)
        update_job(job_id, stage="error", error=str(e))
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
        if subtitle_temps:
            for sub_temp_path, _ in subtitle_temps:
                if os.path.exists(sub_temp_path):
                    try:
                        os.remove(sub_temp_path)
                    except Exception:
                        pass


@router.post("/upload", response_model=ImportJobAccepted, status_code=202)
def upload_video(
    file: UploadFile | None = File(None),
    upload_id: str | None = Form(None),
    title: str | None = Form(None),
    program: str | None = Form(None),
    release: str | None = Form(None),
    description: str | None = Form(None),
    subtitles: List[UploadFile] = File(None),
):
    """
    Upload une vidéo en HTTP et enregistre une tâche d'import suivie en
    arrière-plan (normalisation automatique si requise) — voir
    `_run_video_import_job` et `GET /api/import-jobs`.
    """
    # `upload_id` : fichier déjà reçu par morceaux (app/utils/staged_uploads.py) ;
    # sinon multipart classique — comportement historique conservé.
    temp_path, filename = receive_single_upload(file, upload_id)

    subtitle_temps: list[tuple[str, str]] = []
    if subtitles:
        for sub_file in subtitles:
            if sub_file.filename:
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f"_{sub_file.filename}")
                shutil.copyfileobj(sub_file.file, tmp)
                tmp.close()
                subtitle_temps.append((tmp.name, sub_file.filename))

    job_id = create_job("video", filename, title or Path(filename).stem)
    future = ffmpeg_executor.submit(
        _run_video_import_job,
        job_id,
        temp_path,
        filename,
        title,
        program,
        release,
        description,
        subtitle_temps,
    )
    register_job_future(job_id, future)
    return {"job_id": job_id}


@router.get("", response_model=List[VideoResponse])
def list_videos(
    search: str | None = None,
    program: str | None = None,
    release: str | None = None,
    sort_by: str = "imported_at",
    order: str = "desc",
    db: Session = Depends(get_db),
):
    """
    Récupère la liste des vidéos de la bibliothèque avec filtres et tris.
    """
    query = db.query(Video)

    if search:
        query = query.filter(Video.title.ilike(f"%{search}%"))
    if program:
        query = query.filter(Video.program == program)
    if release:
        query = query.filter(Video.release == release)

    # Tris
    if sort_by == "title":
        col = Video.title
    elif sort_by == "duration":
        col = Video.duration_seconds
    else:
        col = Video.imported_at

    if order == "asc":
        query = query.order_by(col.asc())
    else:
        query = query.order_by(col.desc())

    return query.all()


@router.get("/programs", response_model=List[str])
def list_programs(db: Session = Depends(get_db)):
    """Catégories (programmes) réellement présentes dans la bibliothèque, triées.

    Remplace les catégories jadis codées en dur (RPM/Sprint/The Trip) : le champ
    `program` est un libellé LIBRE saisi par l'utilisateur ; cet endpoint alimente
    la liste de suggestions (datalist) et le regroupement dynamique côté UI.
    Défini AVANT `/{video_id}` pour que « programs » ne soit pas interprété comme
    un identifiant de vidéo.
    """
    rows = (
        db.query(Video.program)
        .filter(Video.program.isnot(None), Video.program != "")
        .distinct()
        .all()
    )
    return sorted({r[0] for r in rows}, key=str.casefold)


@router.get("/{video_id}", response_model=VideoResponse)
def get_video(video_id: int, db: Session = Depends(get_db)):
    """
    Récupère les détails d'une vidéo spécifique.
    """
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Vidéo non trouvée")
    return video


@router.put("/{video_id}", response_model=VideoResponse)
def update_video(video_id: int, payload: VideoUpdate, db: Session = Depends(get_db)):
    """
    Met à jour les métadonnées modifiables d'une vidéo (titre, programme, release).
    Modifie également le nom physique du fichier sur disque pour rester cohérent avec le titre.
    """
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Vidéo non trouvée")

    # Si le titre change, renommer physiquement le fichier sur disque
    if payload.title is not None and payload.title != video.title:
        old_path = Path(video.file_path)
        if old_path.exists():
            import re
            # Tenter de conserver le même UUID s'il est présent dans le nom de fichier actuel
            match = re.match(r"^video_([a-f0-9]{32})_(.+)$", old_path.name)
            if match:
                uuid_str = match.group(1)
            else:
                uuid_str = uuid.uuid4().hex

            # Nettoyer et formater le nouveau titre pour le nom de fichier
            clean_title = "".join(c for c in payload.title if c.isalnum() or c in (" ", "_", "-")).strip()
            clean_title = clean_title.replace(" ", "_")
            if not clean_title:
                clean_title = "video"

            new_filename = f"video_{uuid_str}_{clean_title}{old_path.suffix}"
            new_path = old_path.parent / new_filename

            if new_path != old_path:
                try:
                    shutil.move(old_path, new_path)
                    video.file_path = str(new_path)
                    logger.info(f"Fichier vidéo physiquement renommé de {old_path.name} à {new_filename}")
                except Exception as e:
                    logger.error(f"Erreur lors du renommage physique du fichier vidéo {old_path} -> {new_path}: {e}")

        video.title = payload.title

    if payload.program is not None:
        video.program = payload.program
    if payload.release is not None:
        video.release = payload.release
    if payload.description is not None:
        video.description = payload.description.strip() if payload.description.strip() else None

    db.commit()
    db.refresh(video)
    # `update_video` reste un endpoint SYNCHRONE (`def`, exécuté dans le
    # threadpool FastAPI) — version thread-safe du broadcast.
    ws_manager.broadcast_threadsafe({"event": "library_change", "reason": "video_updated"})
    return video


@router.delete("/{video_id}")
def delete_video(video_id: int, db: Session = Depends(get_db)):
    """
    Supprime physiquement les fichiers de la vidéo et de sa miniature, puis supprime son entrée en BDD.
    """
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Vidéo non trouvée")

    # Suppression du fichier vidéo
    if video.file_path:
        p = Path(video.file_path)
        if p.exists():
            try:
                os.remove(p)
            except Exception as e:
                logger.error(f"Impossible de supprimer le fichier média {p}: {e}")

    # Suppression de la miniature
    if video.thumbnail_path:
        p = Path(video.thumbnail_path)
        if p.exists():
            try:
                os.remove(p)
            except Exception as e:
                logger.error(f"Impossible de supprimer la miniature {p}: {e}")

    # Suppression de la version web « lisible partout », s'il y en a une
    remove_web_file(video.web_path)

    db.delete(video)
    db.commit()
    ws_manager.broadcast_threadsafe({"event": "library_change", "reason": "video_deleted"})
    return {"message": "Vidéo supprimée avec succès"}


@router.post("/{video_id}/web-rendition", response_model=ImportJobAccepted, status_code=202)
def create_web_rendition(video_id: int, db: Session = Depends(get_db)):
    """Lance la production de la version « lisible partout » (H.264 8 bits,
    ≤ 1080p, AAC) — suivie via `GET /api/import-jobs`, état dans `web_status`.
    La vidéo d'origine n'est jamais modifiée (cf. app/utils/web_profile.py)."""
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Vidéo non trouvée")
    if video.web_safe:
        raise HTTPException(status_code=409, detail="Cette vidéo est déjà lisible sur tous les navigateurs : aucune version web n'est nécessaire.")
    job_id = request_web_rendition(video_id)
    if job_id is None:
        raise HTTPException(status_code=409, detail="Une version web est déjà en cours de production pour cette vidéo.")
    return {"job_id": job_id}


@router.delete("/{video_id}/web-rendition")
def delete_web_rendition(video_id: int, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Vidéo non trouvée")
    remove_web_file(video.web_path)
    video.web_path, video.web_status = None, None
    db.commit()
    ws_manager.broadcast_threadsafe({"event": "library_change", "reason": "web_rendition_deleted"})
    return {"message": "Version web supprimée"}


@router.put("/{video_id}/thumbnail", response_model=VideoResponse)
async def upload_video_thumbnail(video_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Miniature manuelle. Permet à un admin
    de fournir lui-même une image, exactement comme _import_background_image()
    le fait déjà pour un fond fixe : aucun décodage vidéo requis, seulement
    Pillow, donc disponible sur toutes les plateformes sans exception.
    """
    from PIL import Image, UnidentifiedImageError

    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Vidéo non trouvée")

    try:
        img = Image.open(file.file)
        img.verify()
        file.file.seek(0)
        img = Image.open(file.file).convert("RGB")
    except (UnidentifiedImageError, OSError):
        raise HTTPException(status_code=400, detail="Fichier image invalide")

    thumbnails_dir = Path(settings.thumbnails_dir)
    thumbnails_dir.mkdir(parents=True, exist_ok=True)

    # Gabarit haute résolution 1080p (LANCZOS) pour un rendu d'une netteté
    # cristalline sur écrans Retina/Haute densité (tablettes 2.8K, TV 4K),
    # évitant le flou de mise à l'échelle d'une miniature 360p étirée en héros.
    img.thumbnail((1920, 1080), Image.Resampling.LANCZOS)
    new_thumb_path = thumbnails_dir / f"thumb_{uuid.uuid4().hex}.jpg"
    img.save(new_thumb_path, "JPEG", quality=92, optimize=True)

    old_thumb_path = Path(video.thumbnail_path) if video.thumbnail_path else None
    video.thumbnail_path = str(new_thumb_path)
    db.commit()
    db.refresh(video)

    if old_thumb_path and old_thumb_path.exists() and old_thumb_path != new_thumb_path:
        try:
            os.remove(old_thumb_path)
        except Exception as e:
            logger.error(f"Impossible de supprimer l'ancienne miniature {old_thumb_path}: {e}")

    return video


def bg_normalize(video_id: int, actions: list, source_metadata: dict | None = None):
    """
    Tâche en arrière-plan pour normaliser une vidéo existante de manière asynchrone.

    `source_metadata` : l'appelant
    (manual_normalize) a déjà extrait les métadonnées de ce même fichier pour
    décider des `actions` — inutile de relancer ffprobe dessus une seconde
    fois avant même de le déplacer vers son emplacement temporaire.
    """
    db = SessionLocal()
    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            return

        old_path = Path(video.file_path)
        file_id = uuid.uuid4().hex
        clean_name = old_path.name
        temp_dest_path = old_path.parent / f"temp_{file_id}_{clean_name}"

        # Déplacement temporaire
        shutil.move(old_path, temp_dest_path)

        # Cible finale (.mp4)
        new_name = f"video_{file_id}_{old_path.stem}.mp4"
        new_path = old_path.parent / new_name

        try:
            normalize_video(str(temp_dest_path), str(new_path), actions, source_metadata=source_metadata)

            # Re-extraction des métadonnées finales
            meta = extract_metadata(str(new_path))

            # Mettre à jour l'enregistrement DB
            video.file_path = str(new_path)
            video.duration_seconds = meta.get("duration_seconds")
            video.width = meta.get("width")
            video.height = meta.get("height")
            video.codec = meta.get("codec")
            if meta.get("audio_channels") is not None:
                video.audio_channels = meta["audio_channels"]
            if meta.get("audio_codec") is not None:
                video.audio_codec = meta["audio_codec"]
            if meta.get("fps") is not None:
                video.fps = meta["fps"]
            if meta.get("bitrate_kbps") is not None:
                video.bitrate_kbps = meta["bitrate_kbps"]
            if not video.description and meta.get("description"):
                video.description = meta["description"]

            # Régénérer la miniature
            if video.thumbnail_path:
                try:
                    os.remove(video.thumbnail_path)
                except Exception:
                    pass

            try:
                thumb_path = generate_thumbnail(
                    str(new_path), settings.thumbnails_dir, meta["duration_seconds"]
                )
                video.thumbnail_path = thumb_path
            except Exception as te:
                logger.error(f"Miniature post-normalisation échouée: {te}")

            db.commit()
            logger.info(f"Vidéo ID {video_id} normalisée avec succès en tâche de fond.")
        finally:
            if temp_dest_path.exists():
                os.remove(temp_dest_path)

    except Exception as e:
        logger.error(f"Erreur lors de la normalisation en tâche de fond de la vidéo {video_id}: {e}")
    finally:
        db.close()


@router.post("/{video_id}/normalize")
def manual_normalize(
    video_id: int,
    db: Session = Depends(get_db),
):
    """
    Déclenche manuellement la normalisation d'une vidéo si elle n'est pas Direct Play.
    """
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Vidéo non trouvée")

    # Extraire les infos réelles pour vérifier les besoins
    try:
        meta = extract_metadata(video.file_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Impossible d'analyser la vidéo : {e}")

    compat = check_compatibility(meta, video.file_path)
    if not compat["needs_normalization"]:
        return {"message": "La vidéo est déjà compatible Direct Play, aucune action requise."}

    # ffmpeg_executor (mono-thread, partagé avec l'import upload/watcher) plutôt
    # que BackgroundTasks : BackgroundTasks exécute une fonction sync
    # sur le pool de threads générique de Starlette, PAS sur notre exécuteur
    # dédié — un import en cours au même moment lançait donc un second ffmpeg
    # en parallèle, doublant la charge CPU sur le Wyse. submit() sans .result()
    # garde ce déclenchement non bloquant pour la réponse HTTP (la tâche
    # patiente dans la file de l'exécuteur si celui-ci est déjà occupé,
    # plutôt que de démarrer un second processus ffmpeg en parallèle).
    ffmpeg_executor.submit(bg_normalize, video_id, compat["actions"], meta)
    return {"message": "La tâche de normalisation a été démarrée en tâche de fond."}


@router.get("/{video_id}/subtitles", response_model=List[VideoSubtitleResponse])
def list_subtitles(video_id: int, db: Session = Depends(get_db)):
    """Liste les pistes de sous-titres associées à une vidéo."""
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Vidéo non trouvée")
    items = []
    for sub in video.subtitles:
        items.append(
            VideoSubtitleResponse(
                id=sub.id,
                video_id=sub.video_id,
                language_code=sub.language_code,
                language_label=sub.language_label,
                format=sub.format,
                vtt_url=f"/api/videos/{video_id}/subtitles/{sub.id}/vtt",
            )
        )
    return items


@router.post("/{video_id}/subtitles", response_model=VideoSubtitleResponse)
async def upload_subtitle(
    video_id: int,
    file: UploadFile = File(...),
    language_code: str | None = Form(None),
    language_label: str | None = Form(None),
    db: Session = Depends(get_db),
):
    """Importe un fichier .srt ou .vtt pour une vidéo, le convertit en WebVTT si nécessaire et l'enregistre."""
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Vidéo non trouvée")

    filename = file.filename or "subtitles.srt"
    ext = Path(filename).suffix.lower()
    if ext not in (".srt", ".vtt"):
        raise HTTPException(status_code=400, detail="Seuls les formats .srt et .vtt sont acceptés.")

    content_bytes = await file.read()
    try:
        content_str = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        content_str = content_bytes.decode("latin-1", errors="replace")

    vtt_content = convert_srt_to_vtt(content_str)

    # Détection automatique de la langue si non fournie
    detected_code, detected_label = detect_language_from_filename(filename)
    final_code = (language_code or detected_code).strip().lower()
    final_label = language_label or LANGUAGE_MAP.get(final_code, detected_label)

    subtitles_dir = get_subtitles_directory()
    out_filename = f"video_{video_id}_{final_code}_{uuid.uuid4().hex[:8]}.vtt"
    out_path = subtitles_dir / out_filename
    out_path.write_text(vtt_content, encoding="utf-8")

    sub = VideoSubtitle(
        video_id=video_id,
        language_code=final_code,
        language_label=final_label,
        file_path=str(out_path.resolve()),
        format="vtt",
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)

    await ws_manager.broadcast({"type": "library_change"})

    return VideoSubtitleResponse(
        id=sub.id,
        video_id=sub.video_id,
        language_code=sub.language_code,
        language_label=sub.language_label,
        format=sub.format,
        vtt_url=f"/api/videos/{video_id}/subtitles/{sub.id}/vtt",
    )


@router.delete("/{video_id}/subtitles/{subtitle_id}")
async def delete_subtitle(video_id: int, subtitle_id: int, db: Session = Depends(get_db)):
    """Supprime une piste de sous-titres sur disque et en base."""
    sub = db.query(VideoSubtitle).filter(VideoSubtitle.id == subtitle_id, VideoSubtitle.video_id == video_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Piste de sous-titres non trouvée")

    file_p = Path(sub.file_path)
    if file_p.exists():
        try:
            file_p.unlink()
        except Exception as e:
            logger.warning("Impossible de supprimer le fichier VTT %s : %s", file_p, e)

    db.delete(sub)
    db.commit()

    await ws_manager.broadcast({"type": "library_change"})
    return {"status": "ok"}


@router.get("/{video_id}/subtitles/{subtitle_id}/vtt")
def get_subtitle_vtt(video_id: int, subtitle_id: int, db: Session = Depends(get_db)):
    """Sert le fichier WebVTT pour les balises HTML5 <track> avec les bons en-têtes CORS et Content-Type."""
    sub = db.query(VideoSubtitle).filter(VideoSubtitle.id == subtitle_id, VideoSubtitle.video_id == video_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Piste de sous-titres non trouvée")

    file_p = Path(sub.file_path)
    if not file_p.exists():
        raise HTTPException(status_code=404, detail="Fichier de sous-titres manquant sur disque")

    return FileResponse(
        str(file_p),
        media_type="text/vtt; charset=utf-8",
        headers={
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "public, max-age=3600",
        },
    )

