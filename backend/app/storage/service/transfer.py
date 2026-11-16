"""Parcours, import, indexation et export entre Bobine et un support."""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
from typing import Any, Callable

from app.devices.base import DeviceError
from app.storage import fsadvisor, library, paths, transfer
from app.storage.lsblk import media_for_kind
from app.storage.types import Volume

logger = logging.getLogger(__name__)


def _export_items(kind: str, ids: list[int]) -> list[tuple[str, str]]:
    from app.database import SessionLocal
    from app.models import AudioTrack, RadioTrack, Video

    model = {"video": Video, "audio": AudioTrack, "radio": RadioTrack}.get(kind)
    if model is None:
        raise transfer.TransferError("bad_kind", "Nature d'export inconnue.", 400)
    with SessionLocal() as db:
        rows = db.query(model).filter(model.id.in_(ids)).all()
        return [(row.file_path, paths.safe_dest_name(f"{row.title}{os.path.splitext(row.file_path)[1].lower()}"))
                for row in rows if row.storage_id is None and os.path.isfile(row.file_path)]


class TransferMixin:
    async def browse(self, key: str, path: str | None, offset: int, limit: int, show_hidden: bool, media_only: bool) -> dict[str, Any]:
        from app.database import SessionLocal

        source = self._source(key)
        self.touch(key)
        listing = await asyncio.to_thread(
            paths.list_directory, source.root, path, offset=offset, limit=limit, show_hidden=show_hidden, media_only=media_only
        )

        def _annotate() -> dict[str, dict[str, Any]]:
            if source.volume is None:
                return {}
            with SessionLocal() as db:
                lib = library.get_by_uuid(db, source.volume.fs_uuid)
                if lib is None:
                    return {}
                rels = [f"{listing.path}/{e.name}" if listing.path else e.name for e in listing.entries if e.type == "file"]
                return library.indexed_lookup(db, lib.id, rels)

        indexed = await asyncio.to_thread(_annotate)
        entries = []
        for e in listing.entries:
            rel = f"{listing.path}/{e.name}" if listing.path else e.name
            item = {"name": e.name, "type": e.type, "size": e.size, "mtime": e.mtime, "media": e.media, "hidden": e.hidden, "path": rel}
            item.update(indexed.get(rel, {"indexed": False}) if e.type == "file" else {})
            entries.append(item)
        return {
            "path": listing.path, "parent": listing.parent, "entries": entries, "total": listing.total, "offset": listing.offset,
            "limit": listing.limit, "truncated": listing.truncated, "skipped_links": listing.skipped_links,
            "portable": source.portable,
        }

    def _mark_busy(self, key: str, job_id: str) -> Callable[[], None]:
        self._busy.setdefault(key, set()).add(job_id)

        def release() -> None:
            def _do() -> None:
                jobs = self._busy.get(key)
                if jobs:
                    jobs.discard(job_id)
                    if not jobs:
                        self._busy.pop(key, None)
                self.touch(key)
                self.notify("jobs")

            try:
                if self._loop is None:
                    raise RuntimeError
                self._loop.call_soon_threadsafe(_do)
            except RuntimeError:
                _do()

        return release

    async def start_import(self, key: str, entries: list[dict[str, str]], kind: str, force: bool = False) -> dict[str, Any]:
        from app.database import SessionLocal
        from app.utils.import_jobs import create_job, register_job_future

        source = self._source(key)
        if not entries:
            raise transfer.TransferError("empty_selection", "Aucun élément sélectionné.", 400)

        def _plan() -> transfer.Plan:
            with SessionLocal() as db:
                return transfer.plan_import(source.root, entries, kind, source.source_id, db, force)

        plan = await asyncio.to_thread(_plan)
        if not plan.units:
            return {"job_id": None, "files": 0, "bytes": 0, "skipped": plan.skipped, "truncated": plan.truncated}
        transfer.check_space(plan.total_bytes)
        label = plan.units[0].title if len(plan.units) == 1 else f"{len(plan.units)} éléments"
        job_id = create_job(transfer.JOB_KIND[kind], label, label, source="storage")
        release = self._mark_busy(key, job_id)
        verify_source = not source.portable
        future = transfer.storage_executor.submit(
            transfer.run_import_job, job_id, source.source_id, plan, verify_source=verify_source, resume=verify_source, on_finished=release
        )
        register_job_future(job_id, future)
        self.notify("jobs")
        return {"job_id": job_id, "files": plan.total_files, "units": len(plan.units), "bytes": plan.total_bytes, "skipped": plan.skipped, "truncated": plan.truncated}

    async def start_index(self, key: str, entries: list[dict[str, str]], kind: str) -> dict[str, Any]:
        """« Utiliser comme extension » : enregistre les médias du support en base, sans copie (lecture directe, lecture seule)."""
        from app.database import SessionLocal
        from app.storage import indexer
        from app.utils.import_jobs import create_job, register_job_future

        if key.startswith("p-"):
            raise DeviceError("portable_no_direct", "Un téléphone ou une tablette ne peut pas servir d'extension de stockage (MTP n'est pas fiable pour la lecture directe) : importez les fichiers.", 409)
        source = self._source(key)
        vol = source.volume
        assert vol is not None

        def _lib_id() -> int | None:
            with SessionLocal() as db:
                lib = library.get_by_uuid(db, vol.fs_uuid)
                return lib.id if lib else None

        lib_id = await asyncio.to_thread(_lib_id)
        if lib_id is None:
            raise DeviceError("not_registered", "Enregistrez d'abord ce support comme bibliothèque externe.", 409)
        if not entries:
            raise transfer.TransferError("empty_selection", "Aucun élément sélectionné.", 400)
        plan = await asyncio.to_thread(indexer.plan_index, source.root, entries, kind)
        if not plan.units:
            return {"job_id": None, "files": 0, "skipped": plan.skipped, "truncated": plan.truncated}
        label = plan.units[0].title if len(plan.units) == 1 else f"{len(plan.units)} éléments"
        job_id = create_job(transfer.JOB_KIND[kind], label, label, source="storage")
        release = self._mark_busy(key, job_id)
        future = transfer.storage_executor.submit(indexer.run_index_job, job_id, lib_id, source.root, plan, release)
        register_job_future(job_id, future)
        self.notify("jobs")
        return {"job_id": job_id, "files": plan.total_files, "units": len(plan.units), "skipped": plan.skipped, "truncated": plan.truncated}

    def _check_export_target(self, key: str, ids: list[int], dest: str | None):
        if key.startswith("p-"):
            raise DeviceError("read_only_device", "Un appareil portable est en lecture seule : aucune écriture.", 409)
        source = self._source(key)
        vol = source.volume
        assert vol is not None
        assessment = fsadvisor.assess_filesystem(vol.fstype, media=media_for_kind(vol.kind), dirty=vol.key in self._dirty)
        if not assessment.write_allowed:
            raise DeviceError("write_refused", "Ce système de fichiers n'est pas fiable en écriture : exportez vers un autre support.", 409)
        if not ids:
            raise transfer.TransferError("empty_selection", "Aucun élément sélectionné.", 400)
        paths.clean_rel_path(dest or "Bobine")
        return source, vol

    async def _open_for_export(self, key: str, vol: Volume, job_id: str, settings: dict) -> None:
        async with self._lock:
            try:
                await self._remount(vol, writable=True, settings=settings)
            except DeviceError:
                from app.utils.import_jobs import cancel_job

                cancel_job(job_id)
                raise
            self._rw_lease.add(key)
            self._mark_busy(key, job_id)

    async def _close_after_export(self, key: str, job_id: str, back_to_read_only: bool, settings: dict) -> None:
        async with self._lock:
            self._rw_lease.discard(key)
            self._busy.get(key, set()).discard(job_id)
            current = self._by_key.get(key)
            if current is not None and current.mounted:
                try:
                    await self._sync_now()
                    if back_to_read_only:
                        await self._remount(current, writable=False, settings=settings)
                except DeviceError as exc:
                    logger.info("Retour en lecture seule impossible : %s", exc.message)
            if not self._busy.get(key):
                self._busy.pop(key, None)
        self.notify("jobs")
        await self.refresh()

    async def start_export(self, key: str, kind: str, ids: list[int], dest: str | None) -> dict[str, Any]:
        """Copie des médias LOCAUX vers le support : écriture temporaire, explicite ; remonte ensuite en lecture seule."""
        from app.utils.import_jobs import create_job, register_job_future

        source, vol = self._check_export_target(key, ids, dest)
        items = await asyncio.to_thread(_export_items, kind, ids)
        if not items:
            raise transfer.TransferError("nothing_to_export", "Aucun média local à exporter dans cette sélection.", 400)
        total = sum(os.path.getsize(p) for p, _ in items)
        free = (await asyncio.to_thread(shutil.disk_usage, source.root)).free
        if free < int(total * 1.02) + 16 * 1024 * 1024:
            raise transfer.TransferError("insufficient_space", "Espace libre insuffisant sur le support.", 409, needed_bytes=total, free_bytes=free)
        settings = await self._effective_settings(vol)
        back_to_read_only = vol.mounted_read_only is not False or bool(settings.get("read_only"))
        job_id = create_job(kind, f"{len(items)} fichier(s) vers le support", "Export", source="storage")
        await self._open_for_export(key, vol, job_id, settings)
        await self.refresh()
        refreshed = self._by_key.get(key)
        root = (refreshed.mountpoint if refreshed else None) or source.root
        loop = self._loop
        assert loop is not None

        def run() -> None:
            try:
                self._run_export(job_id, key, vol, root, dest, items, total)
            finally:
                asyncio.run_coroutine_threadsafe(self._close_after_export(key, job_id, back_to_read_only, settings), loop)

        register_job_future(job_id, transfer.storage_executor.submit(run))
        self.notify("jobs")
        return {"job_id": job_id, "files": len(items), "bytes": total}

    def _run_export(self, job_id: str, key: str, vol: Volume, root: str, dest: str | None, items: list[tuple[str, str]], total: int) -> None:
        from app.database import SessionLocal
        from app.utils.import_jobs import JobCancelledError, is_job_cancelled, update_job

        written = {"n": 0}
        summary: dict[str, Any] = {"exported": 0, "failed": [], "bytes": 0}
        update_job(job_id, stage="copying", bytes_total=total, bytes_done=0, files_total=len(items), files_done=0)

        def bump(n: int) -> None:
            written["n"] += n
            update_job(job_id, bytes_done=written["n"], progress_percent=round(100.0 * written["n"] / max(1, total), 1))

        try:
            target = paths.ensure_dir_within(root, dest or "Bobine")
            for index, (src, name) in enumerate(items):
                if is_job_cancelled(job_id):
                    raise JobCancelledError(job_id)
                update_job(job_id, current_file=name, files_done=index)
                try:
                    result = transfer.export_file(src, target, name, is_cancelled=lambda: is_job_cancelled(job_id), on_bytes=bump)
                    summary["exported"] += 1
                    summary["bytes"] += result["size"]
                except transfer.Cancelled:
                    raise JobCancelledError(job_id)
                except transfer.TransferError as exc:
                    summary["failed"].append({"path": name, "code": exc.code, "message": exc.message})
                    if exc.code in ("dest_io",):
                        break
            if summary["bytes"]:
                with SessionLocal() as db:
                    lib = library.get_by_uuid(db, vol.fs_uuid)
                    if lib is not None:
                        library.add_bytes_written(db, lib.id, summary["bytes"])
                    else:
                        self._written_unregistered[key] = self._written_unregistered.get(key, 0) + summary["bytes"]
            if summary["exported"] == 0 and summary["failed"]:
                update_job(job_id, stage="error", error=summary["failed"][0]["message"], details=summary)
            else:
                update_job(job_id, stage="done", details=summary, files_done=len(items), progress_percent=100.0)
        except JobCancelledError:
            update_job(job_id, stage="cancelled", details=summary)
        except transfer.TransferError as exc:
            update_job(job_id, stage="error", error=exc.message, details=summary)
        except Exception as exc:
            logger.warning("Export vers un support : %s", exc, exc_info=True)
            update_job(job_id, stage="error", error=str(exc), details=summary)
