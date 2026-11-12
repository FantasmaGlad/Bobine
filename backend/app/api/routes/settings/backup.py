"""Sauvegarde, restauration et remise à zéro des données."""

import asyncio
import io
import json
import logging
import os
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import (
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Response,
    UploadFile,
)
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.config import (
    ROOT_DIR,
    _global_config_path,
)
from app.config import (
    settings as runtime_settings,
)
from app.database import _IS_SQLITE, engine, get_db, init_db, release_sqlite_files
from app.utils.activity_log import log_activity
from app.utils.deployment import (
    get_deployment_profile,
    get_profile_handler,
)
from app.utils.version import get_app_version
from app.utils.ws_manager import manager as ws_manager

from .core import _get_sqlite_db_path, router

logger = logging.getLogger(__name__)


def _sanitized_db_bytes(db_path: Path) -> bytes:
    with tempfile.TemporaryDirectory(prefix="bobine_backup_") as tmp_dir:
        copy_path = Path(tmp_dir) / "database.db"
        src = sqlite3.connect(str(db_path))
        dst = sqlite3.connect(str(copy_path))
        try:
            src.backup(dst)
            dst.execute("VACUUM")
        finally:
            dst.close()
            src.close()
        return copy_path.read_bytes()


@router.get("/backup/export")
def export_backup() -> Response:
    """Exporte une archive ZIP de sauvegarde contenant."""
    if not _IS_SQLITE:
        raise HTTPException(status_code=400, detail="L'export de sauvegarde n'est supporté que pour SQLite.")

    db_path = _get_sqlite_db_path()
    if not db_path or not db_path.exists():
        raise HTTPException(status_code=404, detail="Fichier de base de données introuvable.")

    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            conn.execute(text("PRAGMA wal_checkpoint(TRUNCATE);"))
    except Exception as e:
        logger.warning(f"Avertissement lors du checkpoint WAL avant sauvegarde : {e}")

    manifest = {
        "app": "Bobine",
        "version": get_app_version(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "deployment_profile": get_deployment_profile(),
    }

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))
        zf.writestr("database.db", _sanitized_db_bytes(db_path))

        cfg_path = _global_config_path()
        if cfg_path.exists():
            zf.write(cfg_path, arcname="config.toml")
        elif (ROOT_DIR / "config.toml").exists():
            zf.write(ROOT_DIR / "config.toml", arcname="config.toml")

    buf.seek(0)
    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    filename = f"bobine-backup-{timestamp_str}.zip"
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


async def _run_restore_restart():
    await asyncio.sleep(1.0)
    try:
        await ws_manager.broadcast_force_reload()
    except Exception as e:
        logger.warning(f"Échec force_reload après restauration : {e}")
    await asyncio.sleep(1.0)
    get_profile_handler().restart_services()


@router.post("/backup/restore")
async def restore_backup(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Restaure une sauvegarde depuis une archive ZIP uploadée."""
    if not _IS_SQLITE:
        raise HTTPException(status_code=400, detail="La restauration n'est supportée que pour SQLite.")

    db_path = _get_sqlite_db_path()
    if not db_path:
        raise HTTPException(status_code=500, detail="Chemin de la base de données introuvable.")

    work_dir = Path(tempfile.mkdtemp(prefix="bobine-restore-", dir=str(db_path.parent)))
    try:
        db_tmp, config_bytes = await run_in_threadpool(_stage_backup_archive, file.file, work_dir)
        await _restore_database_file(db_tmp, db_path, config_bytes, db, background_tasks)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
    return {
        "status": "ok",
        "message": "Sauvegarde restaurée avec succès. L'application redémarre...",
    }


_MAX_RESTORED_CONFIG_BYTES = 1024 * 1024


def _stage_backup_archive(source, work_dir: Path) -> tuple[Path, bytes | None]:
    archive_path = work_dir / "backup.zip"
    with open(archive_path, "wb") as out:
        shutil.copyfileobj(source, out, 1024 * 1024)
    if archive_path.stat().st_size == 0:
        raise HTTPException(status_code=400, detail="Fichier de sauvegarde vide.")
    if not zipfile.is_zipfile(archive_path):
        raise HTTPException(status_code=400, detail="Le fichier fourni n'est pas une archive ZIP valide.")

    db_tmp = work_dir / "database.db"
    config_bytes: bytes | None = None
    with zipfile.ZipFile(archive_path, "r") as zf:
        names = set(zf.namelist())
        if "database.db" not in names:
            raise HTTPException(status_code=400, detail="Archive invalide : database.db manquant.")
        info = zf.getinfo("database.db")
        if shutil.disk_usage(work_dir).free < info.file_size * 2:
            raise HTTPException(status_code=507, detail="Espace disque insuffisant pour restaurer cette sauvegarde.")
        written = 0
        with zf.open(info) as src, open(db_tmp, "wb") as dst:
            while True:
                block = src.read(1024 * 1024)
                if not block:
                    break
                written += len(block)
                if written > info.file_size:
                    raise HTTPException(status_code=400, detail="Archive invalide : taille de database.db incohérente.")
                dst.write(block)
        if "config.toml" in names:
            cfg_info = zf.getinfo("config.toml")
            if cfg_info.file_size <= _MAX_RESTORED_CONFIG_BYTES:
                with zf.open(cfg_info) as src:
                    config_bytes = src.read(_MAX_RESTORED_CONFIG_BYTES + 1)
                if len(config_bytes) > _MAX_RESTORED_CONFIG_BYTES:
                    config_bytes = None

    with open(db_tmp, "rb") as f:
        if f.read(16) != b"SQLite format 3\x00":
            raise HTTPException(status_code=400, detail="Le fichier database.db n'est pas une base SQLite valide.")
    try:
        con = sqlite3.connect(db_tmp)
        try:
            tables = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            con.close()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Échec de validation de la base de données : {e}")
    if "videos" not in tables and "settings" not in tables:
        raise HTTPException(status_code=400, detail="La base dans l'archive ne contient pas les tables Bobine.")
    return db_tmp, config_bytes


async def _restore_database_file(db_tmp: Path, db_path: Path, config_bytes: bytes | None, db: Session, background_tasks: BackgroundTasks) -> None:
    try:
        log_activity(db, "settings", "Restauration d'une sauvegarde de données")
    except Exception as e:
        logger.warning("Restauration non inscrite au journal d'activité : %s", e)

    try:
        await run_in_threadpool(_replace_database, db_tmp, db_path, config_bytes)
    except Exception:
        logger.exception("Remplacement de la base impossible")
        raise HTTPException(status_code=500, detail="Erreur lors du remplacement de la base : voir le journal technique.")

    background_tasks.add_task(_run_restore_restart)


def _replace_database(db_tmp: Path, db_path: Path, config_bytes: bytes | None) -> None:
    release_sqlite_files(db_path)
    if db_path.exists():
        shutil.copy2(db_path, db_path.with_suffix(".db.bak"))
    shutil.copyfile(db_tmp, db_path)
    if config_bytes:
        cfg_path = _global_config_path()
        try:
            if cfg_path.parent.exists() and os.access(cfg_path.parent, os.W_OK):
                cfg_path.write_bytes(config_bytes)
        except OSError as e:
            logger.warning(f"Impossible d'écrire config.toml restauré : {e}")
    init_db()


class ResetDataRequest(BaseModel):
    confirm: str


def _clean_dir_contents(dir_path: Path) -> None:
    if not dir_path.exists() or not dir_path.is_dir():
        return
    for item in dir_path.iterdir():
        try:
            if item.is_file() or item.is_symlink():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)
        except Exception as e:
            logger.warning(f"Impossible de supprimer {item} lors du reset des données : {e}")


def _wipe_data() -> None:
    dirs_to_clean = [
        runtime_settings.media_dir,
        runtime_settings.watch_dir,
        runtime_settings.thumbnails_dir,
        runtime_settings.backgrounds_dir,
        runtime_settings.backgrounds_watch_dir,
        runtime_settings.audio_dir,
        runtime_settings.audio_watch_dir,
        runtime_settings.radio_dir,
        runtime_settings.radio_covers_dir,
        runtime_settings.radio_announcements_dir,
        runtime_settings.radio_watch_dir,
        runtime_settings.branding_dir,
        runtime_settings.logs_dir,
    ]
    for d in dirs_to_clean:
        _clean_dir_contents(Path(d))
    if _IS_SQLITE:
        db_path = _get_sqlite_db_path()
        if db_path:
            release_sqlite_files(db_path)
            db_path.unlink(missing_ok=True)
        else:
            engine.dispose()
        init_db()


async def _run_reset_data_restart():
    await asyncio.sleep(1.0)
    try:
        await ws_manager.broadcast_force_reload()
    except Exception as e:
        logger.warning(f"Échec force_reload après reset-data : {e}")
    await asyncio.sleep(1.0)
    get_profile_handler().restart_services()


@router.post("/system/reset-data")
async def reset_data_system(payload: ResetDataRequest, background_tasks: BackgroundTasks) -> dict[str, str]:
    """Remise à zéro d'usine : médias, journaux et base de données."""
    phrase = payload.confirm.strip().upper().replace("É", "E")
    if phrase != "REINITIALISER":
        raise HTTPException(status_code=400, detail="Phrase de confirmation incorrecte. Saisissez REINITIALISER.")

    try:
        await run_in_threadpool(_wipe_data)
    except Exception:
        logger.exception("Remise à zéro de la base impossible")
        raise HTTPException(status_code=500, detail="Erreur lors de la remise à zéro de la base : voir le journal technique.")

    background_tasks.add_task(_run_reset_data_restart)
    return {
        "message": "Remise à zéro des données effectuée. L'application redémarre avec une configuration vierge.",
    }
