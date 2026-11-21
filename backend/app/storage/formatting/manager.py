"""Gestionnaire du formatage : plan (lecture seule), exécution en cascade, annulation, vérification après coup."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any
from app.devices.base import DeviceError
from .model import DiskInfo, fingerprint, inventory_digest
from .options import (
    SPECS, LabelError, capacity_limit, confirm_matches, normalize_label,
)
from .refusals import FormatRefusal
from .rules import candidates, evaluate
from .tokens import PlanTokens
from .job import FormatJob, JOB_KEEP_SECONDS, _Cancelled
from .plan import PlanMixin, _env_allow_images
from .steps import StepsMixin
from .verify import VerifyMixin

logger = logging.getLogger(__name__)


class FormatManager(PlanMixin, StepsMixin, VerifyMixin):
    def __init__(self, service: Any, tokens: PlanTokens | None = None) -> None:
        self.svc = service
        self.tokens = tokens or PlanTokens()
        self._gate = asyncio.Lock()
        self._jobs: dict[str, FormatJob] = {}
        self._active: FormatJob | None = None
        self._tasks: set[asyncio.Task[None]] = set()

    async def start(self, key: str, *, token: str | None, fs: str, label: str, confirm_text: str, acknowledged: bool, owner: str) -> dict[str, Any]:
        """Valide la demande, rejoue la cascade sur un inventaire frais, puis lance l'opération."""
        try:
            return await self._start(key, token=token, fs=fs, label=label, confirm_text=confirm_text, acknowledged=acknowledged, owner=owner)
        except FormatRefusal as exc:
            self.svc._log("storage_format_refused", exc.code)
            raise

    async def _start(self, key: str, *, token: str | None, fs: str, label: str, confirm_text: str, acknowledged: bool, owner: str) -> dict[str, Any]:
        label_ok = _checked_request(token, fs, label, acknowledged)
        self.tokens.check_age(token)
        support = await self._precheck(key, fs, confirm_text)
        if self._gate.locked():
            raise FormatRefusal("format_busy_operation")
        await self._gate.acquire()
        job: FormatJob | None = None
        try:
            disk = await self._confirmed_disk(key, token, owner, support)
            job = FormatJob(
                id=uuid.uuid4().hex[:12], key=key, fs=fs, label=label_ok, disk_name=disk.name, started_at=time.time(),
                volume_keys=tuple(self._volume_keys_of(disk)),
            )
            self._launch(job, disk, support)
            return {"job_id": job.id}
        except BaseException:
            if job is None:
                self._gate.release()
            raise

    async def _precheck(self, key: str, fs: str, confirm_text: str) -> dict[str, Any]:
        support = await self.svc.driver.format_support()
        _vol, disk, _disks = await self._resolve(key)
        if disk is None:
            raise FormatRefusal("format_not_found")
        if not confirm_matches(disk, confirm_text):
            raise FormatRefusal("format_confirmation_mismatch")
        if not support.get("tools", {}).get(fs):
            raise FormatRefusal("format_fs_unavailable", package=SPECS[fs].package)
        limit = capacity_limit(fs, disk.size_bytes)
        if limit:
            raise FormatRefusal("format_fs_unavailable", reason=limit)
        return support

    async def _confirmed_disk(self, key: str, token: str, owner: str, support: dict[str, Any]):
        record = self.tokens.consume(token, owner=owner)
        if record.key != key:
            raise FormatRefusal("format_identity_changed")
        _vol, disk, disks = await self._resolve(key)
        ctx = await self._context(disk, support)
        refusal = self._refusal(evaluate(ctx), disk)
        if refusal is not None:
            raise refusal
        assert disk is not None
        if fingerprint(disk) != record.identity or inventory_digest(candidates(disks, allow_images=_env_allow_images())) != record.inventory:
            raise FormatRefusal("format_identity_changed")
        return disk

    def _launch(self, job: FormatJob, disk, support: dict[str, Any]) -> None:
        self._jobs[job.id] = job
        self._active = job
        self.svc._formatting.update(job.volume_keys)
        self.svc._log("storage_format_started", f"{disk.display_name} -> {job.fs}")
        task = asyncio.create_task(self._run(job, disk, support))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        self.svc.notify("format", ["format_started"])

    def _step(self, job: FormatJob, step: str, state: str) -> None:
        job.steps[step] = state
        if state == "running":
            job.stage = step
        self.svc.notify("format")

    def _check_cancel(self, job: FormatJob) -> None:
        if job.cancel_requested and not job.point_of_no_return:
            raise _Cancelled()

    async def _run(self, job: FormatJob, disk: DiskInfo, support: dict[str, Any]) -> None:
        spec = self._spec(job.fs, job.label, disk)
        old_uuids = {p.uuid.lower() for p in disk.partitions if p.uuid}
        try:
            await self._unmount_all(job, disk)
            current = await self._recheck(job, disk, support)
            await self._erase_and_format(job, current, spec)
            report = await self._verify(job, current, spec, old_uuids, support)
            job.report = report
            job.state = "done"
            job.outcome = "verified" if report.get("ok") else "verified_with_warnings"
            self.svc._log("storage_format_done", f"{current.display_name} -> {job.fs} ({job.outcome})")
        except _Cancelled:
            job.state = "cancelled"
            job.outcome = "unchanged"
            job.stage = "cancelled"
            job.report = {"ok": False, "message_key": "cancelled_unchanged"}
            self.svc._log("storage_format_cancelled", disk.display_name)
        except FormatRefusal as exc:
            await self._fail(job, disk, exc.code, exc.message)
        except DeviceError as exc:
            await self._fail(job, disk, exc.code, exc.message)
        except Exception as exc:
            logger.warning("Formatage : échec inattendu : %s", exc, exc_info=True)
            await self._fail(job, disk, "format_failed", "Le formatage a échoué.")
        finally:
            job.finished_at = time.time()
            self.svc._formatting.difference_update(job.volume_keys)
            if self._active is job:
                self._active = None
            if self._gate.locked():
                self._gate.release()
            self._forget_old()
            self.svc.notify("format", ["format_finished"])
            try:
                await self.svc.refresh()
            except Exception:
                logger.debug("Relecture après formatage impossible", exc_info=True)

    async def _fail(self, job: FormatJob, disk: DiskInfo, code: str, message: str) -> None:
        job.state = "failed"
        job.error = {"code": code, "message": message}
        if not job.point_of_no_return:
            job.outcome = "unchanged"
        elif job.steps["table"] != "ok":
            job.outcome = "unchanged" if code == "format_not_authorized" else "partial_unknown"
        elif job.steps["format"] != "ok":
            try:
                await self.svc.driver.wipe_disk(await self._fresh(disk))
                job.outcome = "erased_blank"
            except DeviceError:
                job.outcome = "partial_unknown"
        else:
            job.outcome = "unverified"
        for step, state in job.steps.items():
            if state == "running":
                job.steps[step] = "failed"
        job.report = {"ok": False, "outcome": job.outcome}
        self.svc._log("storage_format_failed", f"{disk.display_name} : {code} ({job.outcome})")

    def _forget_old(self) -> None:
        now = time.time()
        for jid in [j for j, v in self._jobs.items() if v.finished_at and now - v.finished_at > JOB_KEEP_SECONDS]:
            self._jobs.pop(jid, None)

    def job(self, job_id: str) -> FormatJob:
        found = self._jobs.get(job_id)
        if found is None:
            raise FormatRefusal("format_job_not_found")
        return found

    def cancel(self, job_id: str) -> dict[str, Any]:
        job = self.job(job_id)
        if job.state != "running":
            return job.public()
        if job.point_of_no_return:
            raise FormatRefusal("format_cannot_cancel")
        job.cancel_requested = True
        return job.public()

    def active(self) -> FormatJob | None:
        return self._active if self._active and self._active.state == "running" else None


def _checked_request(token: str | None, fs: str, label: str, acknowledged: bool) -> str:
    if not token:
        raise FormatRefusal("format_token_missing")
    if fs not in SPECS:
        raise FormatRefusal("format_fs_unknown")
    try:
        label_ok = normalize_label(fs, label)
    except LabelError as exc:
        raise FormatRefusal("format_label_invalid", label_error=exc.code) from exc
    if not acknowledged:
        raise FormatRefusal("format_ack_missing")
    return label_ok
