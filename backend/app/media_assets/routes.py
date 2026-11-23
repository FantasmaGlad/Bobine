"""Routes d'un espace de médias visuels : envoi, archive, liste, fiche, renommage, suppression et flux."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, Path as PathParam, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.paging import Window, window
from app.api.responses import Message, binary
from app.api.stream_response import range_stream_response
from app.database import SessionLocal, get_db
from app.models import ImportSource
from app.utils._pydantic_compat import OrmModel, _ComputedFieldsCompatMixin, computed_field
from app.utils.archive_import import import_media_archive
from app.utils.executors import ffmpeg_executor
from app.utils.import_jobs import JobCancelledError, create_job, register_job_future, update_job
from app.utils.importer.formats import BACKGROUND_SUPPORTED_EXTENSIONS, is_image_background
from app.utils.staged_uploads import receive_single_upload

from .collection import AssetCollection
from .importer import import_asset

logger = logging.getLogger(__name__)

_IMAGE_CONTENT_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif"}


class AssetUpdate(BaseModel):
    title: str | None = None


class AssetResponse(_ComputedFieldsCompatMixin, OrmModel):
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


def _remove_temp(path: str) -> None:
    if os.path.exists(path):
        try:
            os.remove(path)
        except Exception as exc:
            logger.debug("Fichier temporaire d'import non supprimé %s : %s", path, exc)


def _rename(collection: AssetCollection, asset_id: int, title: str) -> None:
    with SessionLocal() as db:
        row = db.query(collection.model).filter(collection.model.id == asset_id).first()
        if row:
            row.title = title
            db.commit()


def _import_job(collection: AssetCollection, job_id: str, temp_path: str, filename: str, title: str | None) -> None:
    try:
        asset = import_asset(collection, temp_path, filename, ImportSource.upload, job_id=job_id)
        if title:
            _rename(collection, asset.id, title)
        update_job(job_id, stage="done", result_id=asset.id)
    except JobCancelledError:
        logger.info("Import %s %s annulé.", collection.key, job_id)
        update_job(job_id, stage="cancelled")
    except Exception as e:
        logger.error("Import %s (job %s) échoué : %s", collection.key, job_id, e, exc_info=True)
        update_job(job_id, stage="error", error=str(e))
    finally:
        _remove_temp(temp_path)


def _archive_job(collection: AssetCollection, job_id: str, archive_path: str) -> None:
    try:
        assets = import_media_archive(
            archive_path, job_id, BACKGROUND_SUPPORTED_EXTENSIONS,
            lambda path, name: import_asset(collection, path, name, ImportSource.upload, job_id=job_id), collection.archive_label,
        )
        update_job(job_id, stage="done", result_id=assets[0].id)
    except JobCancelledError:
        update_job(job_id, stage="cancelled")
    except Exception as e:
        logger.error("Import d'une archive %s (job %s) échoué : %s", collection.key, job_id, e, exc_info=True)
        update_job(job_id, stage="error", error=str(e))


def _unlink(path: str | None, what: str) -> None:
    if path and Path(path).exists():
        try:
            os.remove(path)
        except Exception as e:
            logger.error("Impossible de supprimer le %s %s : %s", what, path, e)


def asset_router(collection: AssetCollection) -> APIRouter:
    router = APIRouter(prefix=collection.route_prefix, tags=[collection.key])
    model = collection.model
    label = collection.label.lower()
    item = f"/{{{collection.id_param}}}"

    def asset_id_param():
        return PathParam(alias=collection.id_param)

    def one_or_404(db: Session, asset_id: int):
        row = db.query(model).filter(model.id == asset_id).first()
        if not row:
            raise HTTPException(status_code=404, detail=collection.not_found)
        return row

    @router.post("/upload", response_model=ImportJobAccepted, status_code=202,
                 description=f"Envoi d'un {label}, traité en arrière-plan : suivi par `GET /api/import-jobs`.")
    def upload(file: UploadFile | None = File(None), upload_id: str | None = Form(None), title: str | None = Form(None)):
        temp_path, filename = receive_single_upload(file, upload_id)
        job_id = create_job(collection.job_kind, filename, title or Path(filename).stem)
        register_job_future(job_id, ffmpeg_executor.submit(_import_job, collection, job_id, temp_path, filename, title), [temp_path])
        return {"job_id": job_id}

    @router.post("/upload-zip", response_model=ImportJobAccepted, status_code=202,
                 description=f"Import d'une archive (ZIP ou tar) d'images et de vidéos : un {label} par fichier, en une seule tâche.")
    def upload_zip(file: UploadFile | None = File(None), upload_id: str | None = Form(None)):
        temp_path, filename = receive_single_upload(file, upload_id, forced_suffix=".zip")
        job_id = create_job(collection.job_kind, filename, Path(filename).stem)
        register_job_future(job_id, ffmpeg_executor.submit(_archive_job, collection, job_id, temp_path), [temp_path])
        return {"job_id": job_id}

    @router.get("", response_model=List[AssetResponse], description=f"{collection.plural}, du plus récent au plus ancien.")
    def list_assets(db: Session = Depends(get_db), page: Window = Depends(window)):
        return page.rows(db.query(model).order_by(model.imported_at.desc(), model.id.desc()))

    @router.get(item, response_model=AssetResponse, description=f"Fiche d'un {label}.")
    def get_asset(asset_id: int = asset_id_param(), db: Session = Depends(get_db)):
        return one_or_404(db, asset_id)

    @router.put(item, response_model=AssetResponse, description=f"Renomme un {label}.")
    def update_asset(payload: AssetUpdate, asset_id: int = asset_id_param(), db: Session = Depends(get_db)):
        row = one_or_404(db, asset_id)
        if payload.title is not None and payload.title.strip():
            row.title = payload.title.strip()
        db.commit()
        db.refresh(row)
        return row

    @router.delete(item, response_model=Message, description=f"Supprime un {label}, son fichier et sa miniature.")
    def delete_asset(asset_id: int = asset_id_param(), db: Session = Depends(get_db)):
        row = one_or_404(db, asset_id)
        _unlink(row.file_path, "fichier")
        _unlink(row.thumbnail_path, "miniature")
        db.delete(row)
        db.commit()
        return {"message": collection.deleted}

    @router.head(f"{item}/stream", include_in_schema=False)
    @router.get(f"{item}/stream", description=f"Flux d'un {label}, image ou vidéo.",
                **binary("video/mp4", "image/jpeg", "image/png", "image/webp", "image/gif"))
    async def stream_asset(request: Request, asset_id: int = asset_id_param(), db: Session = Depends(get_db)):
        row = await run_in_threadpool(lambda: db.query(model).filter(model.id == asset_id).first())
        if not row:
            raise HTTPException(status_code=404, detail=collection.not_found)
        suffix = Path(row.file_path).suffix.lower()
        content_type = _IMAGE_CONTENT_TYPES.get(suffix) or ("video/webm" if suffix == ".webm" else "video/mp4")
        return await range_stream_response(Path(row.file_path), request, content_type)

    return router
