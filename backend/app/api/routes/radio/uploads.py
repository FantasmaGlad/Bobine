"""API d'envoi de pistes musicales, fichiers ou archive, importées en tâche de fond."""

import logging
import shutil
import tempfile
from pathlib import Path
from typing import List

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.utils.executors import io_executor
from app.utils.import_jobs import create_job, update_job
from app.utils.radio_importer import import_radio_tracks_from_files, import_radio_tracks_from_zip
from app.utils.staged_uploads import receive_single_upload

from .schemas import ImportJobAccepted

logger = logging.getLogger(__name__)

router = APIRouter()


def _run_files_import_job(job_id: str, tmp_dir: Path, temp_paths: list[str]) -> None:
    try:
        tracks = import_radio_tracks_from_files(temp_paths, job_id=job_id)
        update_job(job_id, stage="done", result_id=tracks[0].id if tracks else None)
    except Exception as e:
        logger.error(f"Import radio (job {job_id}) échoué : {e}", exc_info=True)
        update_job(job_id, stage="error", error=str(e))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _run_zip_import_job(job_id: str, temp_path: str) -> None:
    try:
        tracks = import_radio_tracks_from_zip(temp_path, job_id=job_id)
        update_job(job_id, stage="done", result_id=tracks[0].id if tracks else None)
    except Exception as e:
        logger.error(f"Import radio ZIP (job {job_id}) échoué : {e}", exc_info=True)
        update_job(job_id, stage="error", error=str(e))


@router.post("/tracks/upload", response_model=ImportJobAccepted, status_code=202)
def upload_tracks(files: List[UploadFile] = File(...)):
    """Import multi-fichiers de morceaux (tous formats audio), traité en arrière-plan — voir GET /api/import-jobs."""
    tmp_dir = Path(tempfile.mkdtemp(prefix="olmc_radio_upload_"))
    temp_paths = []
    try:
        for f in files:
            dest = tmp_dir / Path(f.filename).name
            with open(dest, "wb") as out:
                shutil.copyfileobj(f.file, out)
            temp_paths.append(str(dest))
    except Exception as e:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise HTTPException(status_code=422, detail=str(e))

    label = Path(files[0].filename).name if files else "morceaux"
    job_id = create_job("radio", label, label)
    io_executor.submit(_run_files_import_job, job_id, tmp_dir, temp_paths)
    return {"job_id": job_id}


@router.post("/tracks/upload-zip", response_model=ImportJobAccepted, status_code=202)
def upload_tracks_zip(file: UploadFile | None = File(None), upload_id: str | None = Form(None)):
    """Import d'une archive ZIP de morceaux, traité en arrière-plan."""
    temp_path, filename = receive_single_upload(file, upload_id, forced_suffix=".zip")

    job_id = create_job("radio", filename or "archive.zip", filename)
    io_executor.submit(_run_zip_import_job, job_id, temp_path)
    return {"job_id": job_id}
