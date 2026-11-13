import os
import logging
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.paging import Window, window
from app.database import get_db, SessionLocal
from app.models import Background, ImportSource
from app.utils.importer.background import import_background
from app.utils.importer.formats import is_image_background
from app.utils.executors import ffmpeg_executor
from app.utils.archive_import import import_media_archive
from app.utils import media_formats
from app.utils.staged_uploads import receive_single_upload
from app.utils.import_jobs import create_job, update_job, register_job_future, JobCancelledError
from app.utils._pydantic_compat import OrmModel, _ComputedFieldsCompatMixin, computed_field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/backgrounds", tags=["backgrounds"])


class BackgroundUpdate(BaseModel):
    title: str | None = None


class BackgroundResponse(_ComputedFieldsCompatMixin, OrmModel):
    id: int
    file_path: str
    title: str
    duration_seconds: float | None
    thumbnail_path: str | None

    @computed_field
    @property
    def is_image(self) -> bool:
        return is_image_background(self.file_path)


class ImportJobAccepted(BaseModel):
    job_id: str


def _run_background_import_job(job_id: str, temp_path: str, filename: str, title: str | None) -> None:
    try:
        background = import_background(temp_path, filename, ImportSource.upload, job_id=job_id)

        if title:
            db = SessionLocal()
            try:
                db_bg = db.query(Background).filter(Background.id == background.id).first()
                if db_bg:
                    db_bg.title = title
                    db.commit()
            finally:
                db.close()

        update_job(job_id, stage="done", result_id=background.id)
    except JobCancelledError:
        logger.info(f"Tâche d'import du fond animé {job_id} annulée.")
        update_job(job_id, stage="cancelled")
    except Exception as e:
        logger.error(f"Erreur lors de l'upload et de l'import du fond animé (job {job_id}): {e}", exc_info=True)
        update_job(job_id, stage="error", error=str(e))
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception as exc:
                logger.debug("_run_background_import_job : %s", exc)


@router.post("/upload", response_model=ImportJobAccepted, status_code=202)
def upload_background(
    file: UploadFile | None = File(None),
    upload_id: str | None = Form(None),
    title: str | None = Form(None),
):
    """Upload web d'un fond animé — traité en arrière-plan, voir `_run_background_import_job` et `GET /api/import-jobs`."""
    temp_path, filename = receive_single_upload(file, upload_id)

    job_id = create_job("background", filename, title or Path(filename).stem)
    future = ffmpeg_executor.submit(_run_background_import_job, job_id, temp_path, filename, title)
    register_job_future(job_id, future, [temp_path])
    return {"job_id": job_id}


def _run_background_archive_job(job_id: str, archive_path: str) -> None:
    try:
        backgrounds = import_media_archive(
            archive_path, job_id, media_formats.VIDEO | {".webm"} | media_formats.IMAGE,
            lambda path, name: import_background(path, name, ImportSource.upload, job_id=job_id), "d'ambiance",
        )
        update_job(job_id, stage="done", result_id=backgrounds[0].id)
    except JobCancelledError:
        update_job(job_id, stage="cancelled")
    except Exception as e:
        logger.error(f"Import d'une archive de fonds (job {job_id}) échoué : {e}", exc_info=True)
        update_job(job_id, stage="error", error=str(e))


@router.post("/upload-zip", response_model=ImportJobAccepted, status_code=202)
def upload_backgrounds_archive(file: UploadFile | None = File(None), upload_id: str | None = Form(None)):
    """Import d'une archive (ZIP ou tar) de fonds animés et d'images : un fond par fichier, en une seule tâche."""
    temp_path, filename = receive_single_upload(file, upload_id, forced_suffix=".zip")
    job_id = create_job("background", filename, Path(filename).stem)
    future = ffmpeg_executor.submit(_run_background_archive_job, job_id, temp_path)
    register_job_future(job_id, future, [temp_path])
    return {"job_id": job_id}


@router.get("", response_model=List[BackgroundResponse])
def list_backgrounds(db: Session = Depends(get_db), page: Window = Depends(window)):
    return page.rows(db.query(Background).order_by(Background.imported_at.desc(), Background.id.desc()))


@router.get("/{background_id}", response_model=BackgroundResponse)
def get_background(background_id: int, db: Session = Depends(get_db)):
    background = db.query(Background).filter(Background.id == background_id).first()
    if not background:
        raise HTTPException(status_code=404, detail="Fond animé non trouvé")
    return background


@router.put("/{background_id}", response_model=BackgroundResponse)
def update_background(background_id: int, payload: BackgroundUpdate, db: Session = Depends(get_db)):
    background = db.query(Background).filter(Background.id == background_id).first()
    if not background:
        raise HTTPException(status_code=404, detail="Fond animé non trouvé")
    if payload.title is not None and payload.title.strip():
        background.title = payload.title.strip()
    db.commit()
    db.refresh(background)
    return background


@router.delete("/{background_id}")
def delete_background(background_id: int, db: Session = Depends(get_db)):
    background = db.query(Background).filter(Background.id == background_id).first()
    if not background:
        raise HTTPException(status_code=404, detail="Fond animé non trouvé")

    if background.file_path:
        p = Path(background.file_path)
        if p.exists():
            try:
                os.remove(p)
            except Exception as e:
                logger.error(f"Impossible de supprimer le fichier de fond {p}: {e}")

    if background.thumbnail_path:
        p = Path(background.thumbnail_path)
        if p.exists():
            try:
                os.remove(p)
            except Exception as e:
                logger.error(f"Impossible de supprimer la miniature {p}: {e}")

    db.delete(background)
    db.commit()
    return {"message": "Fond animé supprimé avec succès"}
