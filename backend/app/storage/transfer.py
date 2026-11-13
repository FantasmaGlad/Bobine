"""Copie vérifiée entre un support externe et le stockage local (import, export)."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from app.api.contract import STORAGE_IMPORT_KINDS
from app.storage import library, paths

logger = logging.getLogger(__name__)

COPY_CHUNK = 4 * 1024 * 1024
RESERVE_BYTES = 1024**3
SPACE_FACTOR = 1.1
STALE_PART_SECONDS = 7 * 24 * 3600

storage_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="bobine-storage")


class TransferError(Exception):
    def __init__(self, code: str, message: str, status: int = 400, **extra: Any):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.extra = extra


class Cancelled(Exception):
    """Transfert annulé par l'utilisateur."""


def staging_root() -> Path:
    from app.config import settings

    root = Path(settings.media_dir).parent / "tmp" / "storage-import"
    (root / "parts").mkdir(parents=True, exist_ok=True)
    return root


def purge_staging(max_age: float = STALE_PART_SECONDS) -> int:
    """Au démarrage : dossiers de travail orphelins supprimés ; `.part` plus vieux que `max_age` supprimés (les récents restent pour la reprise)."""
    root = staging_root()
    removed = 0
    now = time.time()
    for entry in root.iterdir():
        if entry.name == "parts":
            for part in entry.iterdir():
                try:
                    if now - part.stat().st_mtime > max_age:
                        part.unlink()
                        removed += 1
                except OSError:
                    pass
        elif entry.is_dir():
            shutil.rmtree(entry, ignore_errors=True)
            removed += 1
    return removed


def free_bytes(directory: Path | None = None) -> int:
    return shutil.disk_usage(directory or staging_root()).free


def needed_bytes(total: int) -> int:
    return int(total * SPACE_FACTOR) + RESERVE_BYTES


def check_space(total: int, already: int = 0, free: int | None = None) -> None:
    """Lève `insufficient_space` si le disque local ne peut pas accueillir `total` octets (moins ce qui est déjà copié)."""
    available = free_bytes() if free is None else free
    need = needed_bytes(max(0, total - already))
    if available < need:
        raise TransferError(
            "insufficient_space",
            "Espace libre insuffisant sur le stockage local.",
            409,
            needed_bytes=need,
            free_bytes=available,
        )


def _hasher_of_prefix(path: str, length: int) -> "hashlib._Hash":
    digest = hashlib.sha256()
    remaining = length
    with open(path, "rb") as handle:
        while remaining > 0:
            block = handle.read(min(COPY_CHUNK, remaining))
            if not block:
                break
            digest.update(block)
            remaining -= len(block)
    return digest


def _sha_of_prefix(path: str, length: int) -> str:
    return _hasher_of_prefix(path, length).hexdigest()


def _sha_of_file(path: str) -> str:
    return _sha_of_prefix(path, os.path.getsize(path))


def part_path_for(source_id: str, rel: str, size: int, mtime_ns: int) -> Path:
    key = hashlib.sha1(f"{source_id}|{rel}|{size}|{mtime_ns}".encode()).hexdigest()[:24]
    return staging_root() / "parts" / f"{key}.part"


def _source_stat(src: str, verb: str = "impossible") -> os.stat_result:
    try:
        return os.stat(src)
    except OSError as exc:
        raise TransferError("source_io", f"Lecture de la source {verb} : {exc.strerror or exc}", 502) from exc


def _discard(*paths: Path) -> None:
    for path in paths:
        try:
            path.unlink()
        except OSError:
            pass


def _resume_point(src: str, part: Path, meta: Path, size: int, mtime_ns: int, verify_source: bool):
    try:
        saved = json.loads(meta.read_text())
        have = part.stat().st_size
        if saved.get("size") == size and saved.get("mtime_ns") == mtime_ns and 0 < have <= size and verify_source:
            hasher = _hasher_of_prefix(str(part), have)
            if _sha_of_prefix(src, have) == hasher.hexdigest():
                return hasher, have
    except (OSError, ValueError):
        pass
    return hashlib.sha256(), 0


def _copy_blocks(src: str, part: Path, offset: int, digest, chunk: int, is_cancelled, on_bytes) -> int:
    copied = offset
    with open(src, "rb") as reader, open(part, "ab" if offset else "wb") as writer:
        reader.seek(offset)
        while True:
            if is_cancelled():
                raise Cancelled()
            try:
                block = reader.read(chunk)
            except OSError as exc:
                raise TransferError("source_io", f"Lecture de la source interrompue : {exc.strerror or exc}", 502) from exc
            if not block:
                break
            try:
                writer.write(block)
            except OSError as exc:
                raise TransferError("dest_io", f"Écriture locale impossible : {exc.strerror or exc}", 507) from exc
            digest.update(block)
            copied += len(block)
            on_bytes(len(block))
        writer.flush()
        os.fsync(writer.fileno())
    return copied


def copy_verified(
    src: str,
    dest: str,
    *,
    part: Path,
    verify_source: bool = True,
    resume: bool = True,
    is_cancelled: Callable[[], bool] = lambda: False,
    on_bytes: Callable[[int], None] = lambda n: None,
    chunk: int = COPY_CHUNK,
) -> dict[str, Any]:
    """Copie `src` vers `dest` (via `part`) avec reprise et vérification d'intégrité."""
    before = _source_stat(src)
    size, mtime_ns = before.st_size, before.st_mtime_ns
    meta = Path(str(part) + ".json")
    digest, offset = hashlib.sha256(), 0
    if resume and part.exists() and meta.exists():
        digest, offset = _resume_point(src, part, meta, size, mtime_ns, verify_source)
    if offset == 0:
        _discard(part, meta)
    meta.write_text(json.dumps({"size": size, "mtime_ns": mtime_ns}))
    if offset:
        on_bytes(offset)
    try:
        copied = _copy_blocks(src, part, offset, digest, chunk, is_cancelled, on_bytes)
    except Cancelled:
        _discard(part, meta)
        raise
    after = _source_stat(src)
    if copied != size or after.st_size != size or after.st_mtime_ns != mtime_ns:
        _discard(part, meta)
        raise TransferError("source_changed", "Le fichier a changé pendant la copie : relancez l'import.", 409)
    expected = digest.hexdigest()
    if _sha_of_file(str(part)) != expected or part.stat().st_size != size:
        _discard(part, meta)
        raise TransferError("verify_failed", "La copie ne correspond pas à l'original (vérification SHA-256 échouée).", 502)
    os.replace(part, dest)
    _discard(meta)
    return {"size": size, "sha256": expected, "resumed_from": offset}


@dataclass
class UnitFile:
    rel: str
    absolute: str
    size: int
    mtime_ns: int


@dataclass
class Unit:
    kind: str
    title: str
    files: list[UnitFile]
    key: str

    @property
    def total(self) -> int:
        return sum(f.size for f in self.files)


@dataclass
class Plan:
    units: list[Unit] = field(default_factory=list)
    skipped: list[dict[str, str]] = field(default_factory=list)
    truncated: bool = False

    @property
    def total_bytes(self) -> int:
        return sum(u.total for u in self.units)

    @property
    def total_files(self) -> int:
        return sum(len(u.files) for u in self.units)


KIND_TO_MEDIA = dict(zip(STORAGE_IMPORT_KINDS, ({"video"}, {"audio"}, {"audio"})))
JOB_KIND = {"video": "video", "radio": "radio", "audio_course": "audio"}


def _file(root: str, rel: str, absolute: str) -> UnitFile | None:
    try:
        st = os.stat(absolute)
    except OSError:
        return None
    return UnitFile(rel, absolute, st.st_size, st.st_mtime_ns)


def plan_import(root: str, entries: list[dict[str, str]], kind: str, source_id: str, db=None, force: bool = False) -> Plan:
    """Transforme la sélection (fichiers/dossiers) en unités d'import d'UNE nature (`video`, `audio_course`, `radio`)."""
    if kind not in KIND_TO_MEDIA:
        raise TransferError("bad_kind", "Nature d'import inconnue.", 400)
    plan = Plan()
    seen: set[str] = set()
    for entry in entries:
        rel = paths.clean_rel_path(entry.get("path"))
        absolute = paths.resolve_within(root, rel)
        if kind == "audio_course" and os.path.isdir(absolute):
            walked = paths.walk_media(root, [rel], KIND_TO_MEDIA[kind])
            plan.truncated |= walked.truncated
            files = [f for f in (_file(root, r, a) for r, a, _, _ in walked.files) if f]
            if not files:
                plan.skipped.append({"path": rel, "reason": "no_media"})
                continue
            title = os.path.basename(absolute.rstrip("/")) or "Cours importé"
            title = title.replace("_", " ").replace("-", " ").strip() or "Cours importé"
            if rel in seen:
                continue
            seen.add(rel)
            mtime = max(f.mtime_ns for f in files)
            if db is not None and not force and library.already_imported(db, source_id, rel, sum(f.size for f in files), mtime, kind):
                plan.skipped.append({"path": rel, "reason": "already_imported"})
                continue
            plan.units.append(Unit(kind, title, files, rel))
            continue
        walked = paths.walk_media(root, [rel], KIND_TO_MEDIA[kind])
        plan.truncated |= walked.truncated
        if not walked.files:
            plan.skipped.append({"path": rel, "reason": "no_media"})
        for r, a, _, _ in walked.files:
            if r in seen:
                continue
            seen.add(r)
            f = _file(root, r, a)
            if f is None:
                plan.skipped.append({"path": r, "reason": "unreadable"})
                continue
            if db is not None and not force and library.already_imported(db, source_id, r, f.size, f.mtime_ns, kind):
                plan.skipped.append({"path": r, "reason": "already_imported"})
                continue
            title = os.path.splitext(os.path.basename(a))[0].replace("_", " ").replace("-", " ").strip()
            plan.units.append(Unit(kind, title or os.path.basename(a), [f], r))
    return plan


def _safe_staged_name(name: str) -> str:
    cleaned = "".join(c for c in name if c.isalnum() or c in (".", "_", "-", " ", "(", ")")).strip()
    return cleaned or "fichier"


def _run_importer(unit, staged: list[str], job_id: str) -> int | None:
    from app.models import ImportSource
    from app.utils.audio_importer import import_audio_course_from_files
    from app.utils.executors import ffmpeg_executor
    from app.utils.importer.video import import_video
    from app.utils.radio_importer import import_radio_tracks_from_files

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
    from app.utils.import_jobs import JobCancelledError, is_job_cancelled, update_job

    total_bytes = plan.total_bytes
    state = {"bytes": 0}
    summary: dict[str, Any] = {"imported": 0, "failed": [], "skipped": list(plan.skipped), "bytes": 0}
    first_result: int | None = None
    work_dir = staging_root() / job_id
    work_dir.mkdir(parents=True, exist_ok=True)
    update_job(job_id, stage="copying", bytes_total=total_bytes, bytes_done=0, files_total=len(plan.units), files_done=0)

    def bump(n: int) -> None:
        state["bytes"] += n
        percent = round(100.0 * state["bytes"] / total_bytes, 1) if total_bytes else None
        update_job(job_id, bytes_done=state["bytes"], progress_percent=percent)

    def cancelled() -> bool:
        return is_job_cancelled(job_id)

    try:
        for index, unit in enumerate(plan.units):
            if cancelled():
                raise JobCancelledError(job_id)
            update_job(job_id, stage="copying", current_file=unit.title, files_done=index)
            staged: list[str] = []
            try:
                _stage_unit(unit, work_dir / f"{index:04d}", source_id, staged, verify_source, resume, cancelled, bump)
                if cancelled():
                    raise JobCancelledError(job_id)
                update_job(job_id, stage="probing", progress_percent=None)
                local_id = _run_importer(unit, staged, job_id)
                first_result = local_id if first_result is None else first_result
                _record_unit(source_id, unit, local_id)
                summary["imported"] += 1
            except (Cancelled, JobCancelledError):
                raise JobCancelledError(job_id)
            except TransferError as exc:
                logger.warning("Import depuis un support : %s (%s)", unit.title, exc.code)
                summary["failed"].append({"path": unit.key, "code": exc.code, "message": exc.message})
                if exc.code in _FATAL_TRANSFER_CODES:
                    break
            except Exception as exc:
                logger.warning("Import depuis un support : %s : %s", unit.title, exc)
                summary["failed"].append({"path": unit.key, "code": "import_failed", "message": str(exc)})
            finally:
                for path in staged:
                    _discard(Path(path))
        summary["bytes"] = state["bytes"]
        _finish_job(job_id, summary, first_result, len(plan.units))
        return summary
    except JobCancelledError:
        update_job(job_id, stage="cancelled", details=summary)
        return summary
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
        on_finished()


def _fsync_dir(directory: str) -> None:
    try:
        fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError as exc:
        logger.warning("fsync du dossier %s impossible : %s", directory, exc)
    finally:
        os.close(fd)


def export_file(
    src: str,
    dest_dir: str,
    name: str,
    *,
    is_cancelled: Callable[[], bool] = lambda: False,
    on_bytes: Callable[[int], None] = lambda n: None,
    chunk: int = COPY_CHUNK,
) -> dict[str, Any]:
    """Copie `src` (local) dans `dest_dir` (support monté en écriture) : nom libre, fichier temporaire puis renommage atomique, fsync, relecture et comparaison SHA-256."""
    dest = paths.unique_dest(dest_dir, paths.safe_dest_name(name))
    tmp = os.path.join(dest_dir, f".bobine-{uuid.uuid4().hex[:10]}.part")
    digest = hashlib.sha256()
    written = 0
    try:
        with open(src, "rb") as reader, open(tmp, "wb") as writer:
            while True:
                if is_cancelled():
                    raise Cancelled()
                block = reader.read(chunk)
                if not block:
                    break
                try:
                    writer.write(block)
                except OSError as exc:
                    raise TransferError("dest_io", f"Écriture sur le support impossible : {exc.strerror or exc}", 507) from exc
                digest.update(block)
                written += len(block)
                on_bytes(len(block))
            writer.flush()
            os.fsync(writer.fileno())
        if os.path.getsize(tmp) != written or _sha_of_file(tmp) != digest.hexdigest():
            raise TransferError("verify_failed", "La copie sur le support ne correspond pas à l'original.", 502)
        os.replace(tmp, dest)
        _fsync_dir(dest_dir)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
    return {"path": dest, "size": written, "sha256": digest.hexdigest()}
