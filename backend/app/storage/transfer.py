"""Tâche d'import depuis un support : mise en transit, import local, bilan."""

from __future__ import annotations

import logging
import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable

from app.storage import library
from app.storage.import_plan import Plan
from app.storage.verified_copy import Cancelled, TransferError, discard, check_space, copy_verified, part_path_for, staging_root

logger = logging.getLogger(__name__)


storage_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="bobine-storage")


def _safe_staged_name(name: str) -> str:
    cleaned = "".join(c for c in name if c.isalnum() or c in (".", "_", "-", " ", "(", ")")).strip()
    return cleaned or "fichier"


def _run_importer(unit, staged: list[str], job_id: str) -> int | None:
    from app.models import ImportSource
    from app.utils.audio_importer import import_audio_course_from_files
    from app.utils.executors import ffmpeg_executor
    from app.utils.importer.video import import_video
    from app.radio.importer import import_radio_tracks_from_files

    if unit.kind == "video":
        video = ffmpeg_executor.submit(import_video, staged[0], os.path.basename(unit.files[0].absolute), ImportSource.upload, job_id).result()
        return video.id
    if unit.kind == "audio_course":
        return import_audio_course_from_files(staged, unit.title, job_id=job_id).id
    tracks = import_radio_tracks_from_files(staged, job_id=job_id)
    return tracks[0].id if tracks else None


def _stage_unit(unit, unit_dir: Path, source_id: str, staged: list[str], verify_source: bool, resume: bool,
                is_cancelled: Callable[[], bool], on_bytes: Callable[[int], None]) -> None:
    unit_dir.mkdir(parents=True, exist_ok=True)
    for f in unit.files:
        check_space(f.size)
        dest = unit_dir / _safe_staged_name(os.path.basename(f.absolute))
        copy_verified(f.absolute, str(dest), part=part_path_for(source_id, f.rel, f.size, f.mtime_ns),
                      verify_source=verify_source, resume=resume and verify_source,
                      is_cancelled=is_cancelled, on_bytes=on_bytes)
        staged.append(str(dest))


def _record_unit(source_id: str, unit, local_id: int | None) -> None:
    from app.database import SessionLocal
    from app.utils.ws_manager import manager as ws_manager

    with SessionLocal() as db:
        library.record_import(db, source_id, unit.key, unit.total, max(f.mtime_ns for f in unit.files), unit.kind, local_id)
    ws_manager.broadcast_threadsafe({"event": "library_change", "reason": "storage_imported"})


def _finish_job(job_id: str, summary: dict[str, Any], first_result: int | None, units: int) -> None:
    from app.utils.import_jobs import update_job

    if summary["imported"] == 0 and summary["failed"]:
        first = summary["failed"][0]
        update_job(job_id, stage="error", error=first["message"], error_code=first["code"], details=summary)
    elif summary["imported"] == 0:
        update_job(job_id, stage="done", details=summary, files_done=units)
    else:
        update_job(job_id, stage="done", result_id=first_result, details=summary, files_done=units, progress_percent=100.0)


_FATAL_TRANSFER_CODES = ("source_io", "insufficient_space", "dest_io")


class _ImportRun:
    """État d'une tâche d'import : octets copiés, bilan, premier média importé."""

    def __init__(self, job_id: str, source_id: str, plan: Plan, verify_source: bool, resume: bool) -> None:
        self.job_id, self.source_id, self.plan = job_id, source_id, plan
        self.verify_source, self.resume = verify_source, resume
        self.bytes = 0
        self.first_result: int | None = None
        self.summary: dict[str, Any] = {"imported": 0, "failed": [], "skipped": list(plan.skipped), "bytes": 0}
        self.work_dir = staging_root() / job_id

    def bump(self, n: int) -> None:
        from app.utils.import_jobs import update_job

        self.bytes += n
        total = self.plan.total_bytes
        update_job(self.job_id, bytes_done=self.bytes, progress_percent=round(100.0 * self.bytes / total, 1) if total else None)

    def cancelled(self) -> bool:
        from app.utils.import_jobs import is_job_cancelled

        return is_job_cancelled(self.job_id)

    def _copy_and_import(self, index: int, unit, staged: list[str]) -> None:
        from app.utils.import_jobs import JobCancelledError, update_job

        _stage_unit(unit, self.work_dir / f"{index:04d}", self.source_id, staged, self.verify_source, self.resume, self.cancelled, self.bump)
        if self.cancelled():
            raise JobCancelledError(self.job_id)
        update_job(self.job_id, stage="probing", progress_percent=None)
        local_id = _run_importer(unit, staged, self.job_id)
        self.first_result = local_id if self.first_result is None else self.first_result
        _record_unit(self.source_id, unit, local_id)
        self.summary["imported"] += 1

    def unit(self, index: int, unit) -> bool:
        """Importe une unité ; False si l'erreur rend la suite inutile."""
        from app.utils.import_jobs import JobCancelledError, update_job

        if self.cancelled():
            raise JobCancelledError(self.job_id)
        update_job(self.job_id, stage="copying", current_file=unit.title, files_done=index)
        staged: list[str] = []
        try:
            self._copy_and_import(index, unit, staged)
        except (Cancelled, JobCancelledError):
            raise JobCancelledError(self.job_id)
        except TransferError as exc:
            logger.warning("Import depuis un support : %s (%s)", unit.title, exc.code)
            self.summary["failed"].append({"path": unit.key, "code": exc.code, "message": exc.message})
            return exc.code not in _FATAL_TRANSFER_CODES
        except Exception as exc:
            logger.warning("Import depuis un support : %s : %s", unit.title, exc)
            self.summary["failed"].append({"path": unit.key, "code": "import_failed", "message": str(exc)})
        finally:
            for path in staged:
                discard(Path(path))
        return True


def run_import_job(
    job_id: str,
    source_id: str,
    plan: Plan,
    *,
    verify_source: bool = True,
    resume: bool = True,
    on_finished: Callable[[], None] = lambda: None,
) -> dict[str, Any]:
    """Exécute le plan : copie vérifiée de chaque unité puis importeur existant."""
    from app.utils.import_jobs import JobCancelledError, update_job

    run = _ImportRun(job_id, source_id, plan, verify_source, resume)
    run.work_dir.mkdir(parents=True, exist_ok=True)
    update_job(job_id, stage="copying", bytes_total=plan.total_bytes, bytes_done=0, files_total=len(plan.units), files_done=0)
    try:
        for index, unit in enumerate(plan.units):
            if not run.unit(index, unit):
                break
        run.summary["bytes"] = run.bytes
        _finish_job(job_id, run.summary, run.first_result, len(plan.units))
        return run.summary
    except JobCancelledError:
        update_job(job_id, stage="cancelled", details=run.summary)
        return run.summary
    finally:
        shutil.rmtree(run.work_dir, ignore_errors=True)
        on_finished()
