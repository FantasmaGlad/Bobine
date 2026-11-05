"""API « Configuration » (`/api/config/*`) : les fichiers JSON de `app/config_files.py`, un par type de réglage."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app import config_files
from app.database import get_db

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("")
def list_config_files() -> dict[str, Any]:
    """Fichiers disponibles et dossier de la copie à jour (lecture seule, jamais relue par Bobine)."""
    return {"schema": config_files.SCHEMA, "files": list(config_files.BUILDERS), "mirror_dir": str(config_files.mirror_dir())}


@router.get("/export")
async def export_config(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Tous les fichiers d'un coup : `{"schema": 1, "files": {"settings.json": {...}, ...}}`."""
    return {"schema": config_files.SCHEMA, "files": await run_in_threadpool(config_files.export_all, db)}


@router.get("/export/{name}")
async def export_config_file(name: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    builder = config_files.BUILDERS.get(name)
    if builder is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "unknown_config_file", "message": f"{name} inconnu.", "allowed": list(config_files.BUILDERS)},
        )
    return await run_in_threadpool(builder, db)
