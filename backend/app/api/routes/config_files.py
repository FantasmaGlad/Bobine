"""API « Configuration » (`/api/config/*`) : les fichiers JSON de `app/config_files.py`, un par type de réglage."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app import config_files
from app.config_apply.context import ConfigErrors
from app.config_apply.runner import apply as apply_configuration
from app.database import get_db

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("")
def list_config_files() -> dict[str, Any]:
    """Fichiers disponibles et dossier de la copie à jour (lecture seule, jamais relue par Bobine)."""
    return {"schema": config_files.SCHEMA, "files": ["manifest.json", *config_files.BUILDERS], "mirror_dir": str(config_files.mirror_dir())}


@router.get("/export")
async def export_config(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Tous les fichiers d'un coup : `{"schema": 2, "files": {"settings.json": {...}, "playlists/video.json": {...}, ...}}`."""
    return {"schema": config_files.SCHEMA, "files": await run_in_threadpool(config_files.export_all, db)}


@router.get("/export/{name:path}")
async def export_config_file(name: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    name = config_files.canonical_name(name)
    if name == "manifest.json":
        return config_files.export_all(db)["manifest.json"]
    builder = config_files.BUILDERS.get(name)
    if builder is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "unknown_config_file", "message": f"{name} inconnu.", "allowed": ["manifest.json", *config_files.BUILDERS]},
        )
    return await run_in_threadpool(builder, db)


@router.post("/apply")
async def apply_config(
    payload: dict[str, Any] = Body(...),
    dry_run: bool = Query(True),
    include_machine: bool = Query(False),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Applique un ou plusieurs fichiers (`{"files": {"settings.json": {...}}}`) en une seule transaction."""
    files = payload.get("files")
    if not isinstance(files, dict) or not files:
        raise HTTPException(status_code=400, detail={"code": "no_files", "message": "Aucun fichier fourni (« files »)."})
    try:
        return await apply_configuration(db, files, dry_run=dry_run, include_machine=include_machine)
    except ConfigErrors as exc:
        raise HTTPException(
            status_code=422, detail={"code": "invalid_config", "message": "Rien n'a été appliqué.", "errors": exc.errors},
        ) from exc
