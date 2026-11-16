"""Envoi de vidéos : un fichier (avec ses sous-titres) ou une archive, importés en tâche suivie."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import List

from fastapi import APIRouter, File, Form, UploadFile

from app.utils.executors import ffmpeg_executor
from app.utils.import_jobs import create_job, register_job_future
from app.utils.staged_uploads import receive_single_upload
from app.utils.subtitles import SUBTITLE_EXTENSIONS
from app.videos.import_jobs import run_video_archive_job, run_video_import_job

from .schemas import ImportJobAccepted

router = APIRouter()


def _stage_subtitles(subtitles: List[UploadFile] | None) -> list[tuple[str, str]]:
    staged: list[tuple[str, str]] = []
    for sub_file in subtitles or []:
        name = Path(sub_file.filename or "").name
        if Path(name).suffix.lower() not in SUBTITLE_EXTENSIONS:
            continue
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=Path(name).suffix.lower())
        shutil.copyfileobj(sub_file.file, tmp)
        tmp.close()
        staged.append((tmp.name, name))
    return staged


@router.post("/upload-zip", response_model=ImportJobAccepted, status_code=202)
def upload_videos_archive(file: UploadFile | None = File(None), upload_id: str | None = Form(None)):
    """Import d'une archive (ZIP ou tar) de vidéos : un cours par fichier, en une seule tâche."""
    temp_path, filename = receive_single_upload(file, upload_id, forced_suffix=".zip")
    job_id = create_job("video", filename, Path(filename).stem)
    future = ffmpeg_executor.submit(run_video_archive_job, job_id, temp_path)
    register_job_future(job_id, future, [temp_path])
    return {"job_id": job_id}


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
    """Upload une vidéo en HTTP et enregistre une tâche d'import suivie en arrière-plan (normalisation automatique si requise) — voir `GET /api/import-jobs`."""
    temp_path, filename = receive_single_upload(file, upload_id)
    subtitle_temps = _stage_subtitles(subtitles)
    job_id = create_job("video", filename, title or Path(filename).stem)
    fields = {"title": title, "program": program, "release": release, "description": description}
    future = ffmpeg_executor.submit(run_video_import_job, job_id, temp_path, filename, fields, subtitle_temps)
    register_job_future(job_id, future, [temp_path, *(path for path, _ in subtitle_temps)])
    return {"job_id": job_id}
