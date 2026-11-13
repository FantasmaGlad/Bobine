from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.responses import CancelledJob
from app.api.paging import Window, window
from app.utils.import_jobs import list_jobs, cancel_job

router = APIRouter(prefix="/api/import-jobs", tags=["import-jobs"])


class ImportJobResponse(BaseModel):
    id: str
    kind: str
    source: str
    filename: str
    title: str | None
    stage: str
    stage_label: str
    error: str | None
    error_code: str | None = None
    error_params: dict | None = None
    result_id: int | None
    created_at: float
    updated_at: float
    queue_position: int | None = None
    progress_percent: float | None = None
    eta_seconds: int | None = None
    speed: str | None = None
    estimated_seconds: float | None = None
    queue_eta_seconds: int | None = None
    bytes_total: int | None = None
    bytes_done: int | None = None
    files_total: int | None = None
    files_done: int | None = None
    current_file: str | None = None
    details: dict | None = None


@router.get("", response_model=List[ImportJobResponse])
def get_import_jobs(page: Window = Depends(window)):
    """File d'attente des imports en direct : uploads web ET dossiers surveillés confondus, triés par ordre de création."""
    return page.items(list_jobs())


@router.delete("/{job_id}", response_model=CancelledJob)
def cancel_import_job(job_id: str):
    """Annule immédiatement une tâche d'importation en cours ou en attente, interrompt FFmpeg le cas échéant et supprime les fichiers temporaires."""
    found = cancel_job(job_id)
    if not found:
        raise HTTPException(status_code=404, detail="Tâche d'importation introuvable ou déjà terminée")
    return {"status": "cancelled", "job_id": job_id}

