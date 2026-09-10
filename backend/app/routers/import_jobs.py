from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

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
    result_id: int | None
    created_at: float
    updated_at: float
    queue_position: int | None = None
    progress_percent: float | None = None
    eta_seconds: int | None = None
    speed: str | None = None
    estimated_seconds: float | None = None
    queue_eta_seconds: int | None = None


@router.get("", response_model=List[ImportJobResponse])
def get_import_jobs():
    """
    File d'attente des imports en direct (réf. mission "voir en direct les
    importations et l'estimation d'où elles en sont") : uploads web ET
    dossiers surveillés confondus, triés par ordre de création. Interrogé par
    polling depuis l'UI d'admin plutôt qu'un canal WebSocket dédié — ces
    tâches évoluent lentement (secondes à dizaines de minutes) comparé au
    reste de l'app, un polling léger suffit largement.
    """
    return list_jobs()


@router.delete("/{job_id}")
def cancel_import_job(job_id: str):
    """
    Annule immédiatement une tâche d'importation en cours ou en attente,
    interrompt FFmpeg le cas échéant et supprime les fichiers temporaires.
    """
    found = cancel_job(job_id)
    if not found:
        raise HTTPException(status_code=404, detail="Tâche d'importation introuvable ou déjà terminée")
    return {"status": "cancelled", "job_id": job_id}

