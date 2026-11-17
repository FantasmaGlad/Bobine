"""API d'envoi de cours audio, fichiers ou archive, importés en tâche de fond."""

import logging
import shutil
import tempfile
from pathlib import Path
from typing import List

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.utils.audio_importer import import_audio_course_from_files, import_audio_course_from_zip
from app.utils.executors import io_executor
from app.utils.import_jobs import create_job, update_job
from app.utils.staged_uploads import receive_single_upload

from .schemas import ImportJobAccepted

logger = logging.getLogger(__name__)

router = APIRouter()


def _run_audio_files_import_job(
    job_id: str, tmp_dir: Path, temp_paths: list[str], title: str, program: str | None, release: str | None
) -> None:
    try:
        course = import_audio_course_from_files(temp_paths, title, program, release, job_id=job_id)
        update_job(job_id, stage="done", result_id=course.id)
    except Exception as e:
        logger.error(f"Erreur lors de l'upload du cours audio (job {job_id}): {e}", exc_info=True)
        update_job(job_id, stage="error", error=str(e))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _run_audio_zip_import_job(
    job_id: str, temp_path: str, title: str, program: str | None, release: str | None
) -> None:
    try:
        course = import_audio_course_from_zip(temp_path, title, program, release, job_id=job_id)
        update_job(job_id, stage="done", result_id=course.id)
    except Exception as e:
        logger.error(f"Erreur lors de l'upload ZIP du cours audio (job {job_id}): {e}", exc_info=True)
        update_job(job_id, stage="error", error=str(e))


@router.post("/upload", response_model=ImportJobAccepted, status_code=202)
def upload_audio_course(
    files: List[UploadFile] = File(...),
    title: str = Form(...),
    program: str | None = Form(None),
    release: str | None = Form(None),
):
    """Import multi-fichiers MP3 d'un cours, traité en arrière-plan — voir `_run_audio_files_import_job` et `GET /api/import-jobs`."""
    if not title.strip():
        raise HTTPException(status_code=422, detail="Le titre du cours est requis")

    tmp_dir = Path(tempfile.mkdtemp(prefix="olmc_audio_upload_"))
    temp_paths = []
    try:
        for f in files:
            dest = tmp_dir / Path(f.filename).name
            with open(dest, "wb") as out:
                shutil.copyfileobj(f.file, out)
            temp_paths.append(str(dest))
    except Exception as e:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        logger.error(f"Erreur lors de la réception de l'upload du cours audio: {e}", exc_info=True)
        raise HTTPException(status_code=422, detail=str(e))

    job_id = create_job("audio", title.strip(), title.strip())
    io_executor.submit(_run_audio_files_import_job, job_id, tmp_dir, temp_paths, title.strip(), program, release)
    return {"job_id": job_id}


@router.post("/upload-zip", response_model=ImportJobAccepted, status_code=202)
def upload_audio_course_zip(
    file: UploadFile | None = File(None),
    upload_id: str | None = Form(None),
    title: str = Form(...),
    program: str | None = Form(None),
    release: str | None = Form(None),
):
    """Import d'une archive ZIP d'un cours complet, traité en arrière-plan — voir `_run_audio_zip_import_job` et `GET /api/import-jobs`."""
    if not title.strip():
        raise HTTPException(status_code=422, detail="Le titre du cours est requis")

    temp_path, _ = receive_single_upload(file, upload_id, forced_suffix=".zip")

    job_id = create_job("audio", title.strip(), title.strip())
    io_executor.submit(_run_audio_zip_import_job, job_id, temp_path, title.strip(), program, release)
    return {"job_id": job_id}
