"""Gestionnaire du formatage : plan (lecture seule), exécution en cascade, annulation, vérification après coup.

Deux phases côté serveur :

1. `plan` ne touche à rien : il relit le support, passe la cascade de vérifications, résume ce qui sera effacé, liste les
   formats possibles avec le verdict du conseiller et délivre un jeton court à usage unique lié à l'identité du support ;
2. `start` exige ce jeton, le format choisi, une étiquette valide et la confirmation saisie, rejoue TOUTE la cascade sur un
   inventaire frais, compare l'identité, puis lance l'opération en arrière-plan.

L'opération ne fait qu'un formatage RAPIDE : table GPT, une partition alignée sur 1 Mio, système de fichiers. Le point de
non-retour est franchi juste avant l'écriture de la table ; avant, l'annulation est possible et le support reste intact ;
après, elle ne l'est plus. Au moindre échec après l'effacement, le support est ramené à l'état vierge plutôt que laissé à
moitié configuré. Tout ce que le support devient est relu et contrôlé (cascade de vérification après coup).
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import secrets
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.devices.base import DeviceError
from app.storage import fsadvisor, library
from app.storage.types import Volume

from . import content as content_mod
from .model import DiskInfo, FormatSpec, fingerprint, hardware_identity, inventory_digest
from .options import (
    ALIGNMENT, SPECS, SUPPORTED, LabelError, capacity_limit, confirm_expected, confirm_matches, mkfs_args, normalize_label,
    option_for, partition_bytes_for,
)
from .refusals import FormatRefusal
from .rules import GuardContext, candidates, evaluate, first_refusal
from .tokens import PlanTokens

logger = logging.getLogger(__name__)

# Étapes de l'opération, dans l'ordre (l'interface les affiche) ; l'effacement commence à « table ».
STEPS = ("unmount", "recheck", "table", "format", "settle", "readback", "mount_ro", "write_test", "back_ro", "health")
POINT_OF_NO_RETURN = "table"
UNMOUNT_TRIES = 4
UNMOUNT_PAUSE = 1.5
SETTLE_SECONDS = 25.0
JOB_KEEP_SECONDS = 600.0
TEST_FILE_BYTES = 64 * 1024
SECTOR = 512

OWN_ENV_IMAGES = "BOBINE_STORAGE_FORMAT_IMAGES"       # essais : autorise les images disque (loop)
OWN_ENV_ONLY = "BOBINE_STORAGE_FORMAT_ONLY"           # essais : liste blanche de périphériques (/dev/loopN,...)


def _env_allow_images() -> bool:
    return os.environ.get(OWN_ENV_IMAGES, "") == "1"


def _env_allowlist() -> frozenset[str] | None:
    raw = os.environ.get(OWN_ENV_ONLY, "").strip()
    return frozenset(p.strip() for p in raw.split(",") if p.strip()) if raw else None


def _media_for_kind(kind: str) -> str:
    return {"hdd": "hdd", "ssd": "ssd"}.get(kind, "flash")


@dataclass
class FormatJob:
    id: str
    key: str
    fs: str
    label: str
    disk_name: str
    started_at: float
    steps: dict[str, str] = field(default_factory=lambda: {s: "pending" for s in STEPS})
    stage: str = "starting"
    state: str = "running"           # running | done | failed | cancelled
    outcome: str | None = None       # verified | verified_with_warnings | unchanged | erased_blank | partial_unknown | unverified
    point_of_no_return: bool = False
    cancel_requested: bool = False
    error: dict[str, str] | None = None
    report: dict[str, Any] | None = None
    finished_at: float | None = None
    volume_keys: tuple[str, ...] = ()

    @property
    def can_cancel(self) -> bool:
        return self.state == "running" and not self.point_of_no_return

    def percent(self) -> int:
        done = sum(1 for v in self.steps.values() if v in ("ok", "warn", "skipped"))
        return int(100 * done / len(STEPS))

    def public(self) -> dict[str, Any]:
        return {
            "job_id": self.id, "state": self.state, "stage": self.stage, "outcome": self.outcome, "percent": self.percent(),
            "steps": [{"id": s, "state": self.steps[s]} for s in STEPS], "can_cancel": self.can_cancel,
            "point_of_no_return": self.point_of_no_return, "error": self.error, "report": self.report,
            "fs": self.fs, "label": self.label,
        }


class _Cancelled(Exception):
    pass


class FormatManager:
    def __init__(self, service: Any, tokens: PlanTokens | None = None) -> None:
        self.svc = service
        self.tokens = tokens or PlanTokens()
        self._gate = asyncio.Lock()
        self._jobs: dict[str, FormatJob] = {}
        self._active: FormatJob | None = None
        self._tasks: set[asyncio.Task[None]] = set()

    # ------------------------------------------------------------------ contexte de la cascade
    async def _registered(self) -> tuple[frozenset[str], dict[str, str]]:
        from app.database import SessionLocal

        def _uuids() -> list[str]:
            with SessionLocal() as db:
                return [lib.fs_uuid.lower() for lib in library.all_libraries(db) if lib.fs_uuid]

        uuids = await asyncio.to_thread(_uuids)
        keys = {(v.fs_uuid or "").lower(): v.key for v in self.svc._by_key.values() if v.fs_uuid}
        return frozenset(uuids), keys

    def _volume_keys_of(self, disk: DiskInfo) -> list[str]:
        return [k for k, v in self.svc._by_key.items() if v.disk == disk.name]

    def _in_use(self, disk: DiskInfo) -> bool:
        for key in self._volume_keys_of(disk):
            if self.svc._busy.get(key) or key in self.svc._ejecting or key in self.svc._rw_lease:
                return True
        return False

    @staticmethod
    def _device_numbers(paths: list[str]) -> dict[str, int]:
        out: dict[str, int] = {}
        for path in paths:
            try:
                out[path] = os.stat(path).st_dev
            except OSError:
                continue
        return out

    async def _context(self, disk: DiskInfo | None, support: dict[str, Any], *, ignore_job: FormatJob | None = None) -> GuardContext:
        protected = self.svc.protected_paths()
        registered, _ = await self._registered()
        mount_devs: dict[str, int] = {}
        protected_devs: frozenset[int] = frozenset()
        if disk is not None:
            mount_devs = await asyncio.to_thread(self._device_numbers, list(disk.mountpoints))
        protected_devs = frozenset((await asyncio.to_thread(self._device_numbers, protected)).values())
        other = self._active is not None and self._active is not ignore_job and self._active.state == "running"
        return GuardContext(
            supported=bool(support.get("supported")), disk=disk, protected_paths=protected, protected_devs=protected_devs,
            mount_devs=mount_devs, registered_uuids=registered, in_use=self._in_use(disk) if disk else False,
            other_format_active=other, allow_images=_env_allow_images(), allowlist=_env_allowlist(),
        )

    async def _resolve(self, key: str) -> tuple[Volume | None, DiskInfo | None, list[DiskInfo]]:
        """Support et disque RELUS dans l'inventaire courant (jamais un chemin envoyé par le client)."""
        if key.startswith("p-"):
            raise FormatRefusal("format_phone")
        vol = self.svc._by_key.get(key)
        disks = await self.svc.driver.disks()
        if vol is None or not vol.disk:
            return vol, None, disks
        for disk in disks:
            if disk.name == vol.disk and any(p.path == vol.device for p in disk.partitions):
                return vol, disk, disks
        return vol, None, disks

    def _refusal(self, checks: list, disk: DiskInfo | None) -> FormatRefusal | None:
        bad = first_refusal(checks)
        if bad is None:
            return None
        extra: dict[str, Any] = {"check": bad.id}
        if bad.actions and disk is not None:
            registered_keys = [
                k for k, v in self.svc._by_key.items()
                if v.disk == disk.name and v.fs_uuid
            ]
            extra["actions"] = [{"id": "unregister", "key": k} for k in registered_keys]
        return FormatRefusal(bad.code or "format_failed", **extra)

    # ------------------------------------------------------------------ phase 1 : plan (aucune écriture)
    async def plan(self, key: str, *, owner: str, travels: list[str], pin_required: bool) -> dict[str, Any]:
        support = await self.svc.driver.format_support()
        vol, disk, disks = await self._resolve(key)
        ctx = await self._context(disk, support)
        checks = evaluate(ctx)
        refusal = self._refusal(checks, disk)
        if refusal is not None:
            raise refusal
        assert disk is not None and vol is not None

        # Contenu : lecture seule uniquement. Un support déjà monté est lu tel quel ; sinon montage en lecture seule.
        reads = await self._content_of(disk)
        # Relecture fraîche : l'identité du plan est celle d'APRÈS la lecture du contenu.
        _, disk, disks = await self._resolve(key)
        if disk is None:
            raise FormatRefusal("format_not_found")
        ctx = await self._context(disk, support)
        refusal = self._refusal(evaluate(ctx), disk)
        if refusal is not None:
            raise refusal

        others = tuple(o for o in travels if o in fsadvisor.OSES and o != "linux")
        media = _media_for_kind(disk.kind)
        recommended = fsadvisor.recommend_format("linux", others, media)
        tools = support.get("tools", {})
        options = [option_for(fs, disk, tool_present=bool(tools.get(fs)), others=others, media=media) for fs in SUPPORTED]
        for opt in options:
            opt["recommended"] = opt["fs"] == recommended["fstype"]
        confirm = confirm_expected(disk)
        token = self.tokens.issue(
            key=key, identity=fingerprint(disk), inventory=inventory_digest(candidates(disks, allow_images=_env_allow_images())), owner=owner
        )
        used = sum(r.get("bytes_used", 0) for r in reads if r.get("readable"))
        return {
            "token": token,
            "expires_in": int(self.tokens.ttl),
            "min_wait": int(self.tokens.min_age),
            "pin_required": pin_required,
            "checks": [{"id": c.id, "ok": c.ok} for c in checks],
            "target": {
                "key": key, "name": disk.display_name, "size_bytes": disk.size_bytes, "kind": disk.kind, "transport": disk.transport,
                "vendor": disk.vendor, "model": disk.model, "table": disk.ptable,
                "partitions": [
                    {"label": p.label, "fstype": p.fstype, "size_bytes": p.size_bytes, "mounted": p.mounted}
                    for p in disk.partitions
                ],
            },
            "content": {"volumes": reads, "bytes_used": used},
            "erases": {"partitions": len(disk.partitions), "files": sum(r.get("files", 0) for r in reads if r.get("readable")),
                       "truncated": any(r.get("truncated") for r in reads if r.get("readable")),
                       "unreadable": any(not r.get("readable") for r in reads)},
            "recommended": recommended["fstype"],
            "recommended_reason": recommended["reason"],
            "options": options,
            "confirm": confirm,
            "alignment_bytes": ALIGNMENT,
            "quick_only": True,
        }

    async def _content_of(self, disk: DiskInfo) -> list[dict[str, Any]]:
        """Résumé du contenu de chaque système de fichiers du disque (montage en lecture seule si nécessaire, rien d'autre)."""
        results: list[dict[str, Any]] = []
        for part in disk.partitions:
            if not part.fstype:
                continue
            entry: dict[str, Any] = {"label": part.label, "fstype": part.fstype, "size_bytes": part.size_bytes}
            mountpoint = part.mountpoints[0] if part.mountpoints else None
            if mountpoint is None:
                vol = next((v for v in self.svc._by_key.values() if v.device == part.path), None)
                if vol is not None:
                    try:
                        await self.svc.mount(vol.key, "ro")
                        vol = self.svc._by_key.get(vol.key) or vol
                        mountpoint = vol.mountpoint
                    except DeviceError as exc:
                        entry["readable"] = False
                        entry["reason"] = exc.code
                else:
                    entry["readable"] = False
                    entry["reason"] = "not_listed"
            if mountpoint:
                try:
                    usage = await asyncio.to_thread(os.statvfs, mountpoint)
                    entry["bytes_used"] = max(0, (usage.f_blocks - usage.f_bfree) * usage.f_frsize)
                    entry["bytes_total"] = usage.f_blocks * usage.f_frsize
                except OSError:
                    pass
                entry.update(await asyncio.to_thread(content_mod.summarize, mountpoint))
            elif "readable" not in entry:
                entry["readable"] = False
                entry["reason"] = "not_mounted"
            results.append(entry)
        return results

    # ------------------------------------------------------------------ phase 2 : exécution
    def _spec(self, fs: str, label: str, disk: DiskInfo) -> FormatSpec:
        spec = SPECS[fs]
        return FormatSpec(
            fs=fs, label=label, udisks_type=spec.udisks_type, partition_guid=spec.partition_guid, partition_name=label[:36],
            mkfs_args=tuple(mkfs_args(fs, partition_bytes_for(disk.size_bytes))), take_ownership=spec.take_ownership,
        )

    async def start(self, key: str, *, token: str | None, fs: str, label: str, confirm_text: str, acknowledged: bool, owner: str) -> dict[str, Any]:
        """Valide la demande, rejoue la cascade sur un inventaire frais, puis lance l'opération. Rien n'est écrit avant.

        Tout refus est journalisé (code seulement : jamais de jeton, de PIN, de numéro de série ni de chemin)."""
        try:
            return await self._start(key, token=token, fs=fs, label=label, confirm_text=confirm_text, acknowledged=acknowledged, owner=owner)
        except FormatRefusal as exc:
            self.svc._log("storage_format_refused", exc.code)
            raise

    async def _start(self, key: str, *, token: str | None, fs: str, label: str, confirm_text: str, acknowledged: bool, owner: str) -> dict[str, Any]:
        # 0. validation de la demande (aucun état modifié, le jeton n'est pas encore brûlé)
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
        self.tokens.check_age(token)
        support = await self.svc.driver.format_support()
        vol, disk, disks = await self._resolve(key)
        if disk is None:
            raise FormatRefusal("format_not_found")
        if not confirm_matches(disk, confirm_text):
            raise FormatRefusal("format_confirmation_mismatch")
        if not support.get("tools", {}).get(fs):
            raise FormatRefusal("format_fs_unavailable", package=SPECS[fs].package)
        limit = capacity_limit(fs, disk.size_bytes)
        if limit:
            raise FormatRefusal("format_fs_unavailable", reason=limit)

        # Une seule opération destructive à la fois : prise atomique du verrou (aucune attente entre le test et la prise).
        if self._gate.locked():
            raise FormatRefusal("format_busy_operation")
        await self._gate.acquire()
        job: FormatJob | None = None
        try:
            # 1. le jeton est brûlé ICI : toute dérive à partir de maintenant impose de recommencer
            record = self.tokens.consume(token, owner=owner)
            if record.key != key:
                raise FormatRefusal("format_identity_changed")
            # 2. relecture au dernier instant, cascade complète, comparaison d'identité
            vol, disk, disks = await self._resolve(key)
            ctx = await self._context(disk, support)
            refusal = self._refusal(evaluate(ctx), disk)
            if refusal is not None:
                raise refusal
            assert disk is not None
            if fingerprint(disk) != record.identity or inventory_digest(candidates(disks, allow_images=_env_allow_images())) != record.inventory:
                raise FormatRefusal("format_identity_changed")

            job = FormatJob(
                id=uuid.uuid4().hex[:12], key=key, fs=fs, label=label_ok, disk_name=disk.name, started_at=time.time(),
                volume_keys=tuple(self._volume_keys_of(disk)),
            )
            self._jobs[job.id] = job
            self._active = job
            self.svc._formatting.update(job.volume_keys)
            self.svc._log("storage_format_started", f"{disk.display_name} -> {fs}")
            task = asyncio.create_task(self._run(job, disk, support))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
            self.svc.notify("format", ["format_started"])
            return {"job_id": job.id}
        except BaseException:
            if job is None:
                self._gate.release()
            raise

    # ------------------------------------------------------------------ déroulement
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
        except Exception as exc:  # noqa: BLE001 - jamais une exception brute : état explicite
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
            except Exception:  # noqa: BLE001
                logger.debug("Relecture après formatage impossible", exc_info=True)

    async def _fail(self, job: FormatJob, disk: DiskInfo, code: str, message: str) -> None:
        job.state = "failed"
        job.error = {"code": code, "message": message}
        if not job.point_of_no_return:
            job.outcome = "unchanged"                    # rien n'a été effacé
        elif job.steps["table"] != "ok":
            # Un refus d'autorisation précède toute écriture ; toute autre panne pendant la table laisse un état incertain.
            job.outcome = "unchanged" if code == "format_not_authorized" else "partial_unknown"
        elif job.steps["format"] != "ok":
            # La table est écrite mais pas le système de fichiers : retour à un support vierge, jamais à moitié configuré.
            try:
                await self.svc.driver.wipe_disk(await self._fresh(disk))
                job.outcome = "erased_blank"
            except DeviceError:
                job.outcome = "partial_unknown"
        else:
            job.outcome = "unverified"                   # formaté, mais la vérification n'a pas pu aboutir
        for step, state in job.steps.items():
            if state == "running":
                job.steps[step] = "failed"
        job.report = {"ok": False, "outcome": job.outcome}
        self.svc._log("storage_format_failed", f"{disk.display_name} : {code} ({job.outcome})")

    def _forget_old(self) -> None:
        now = time.time()
        for jid in [j for j, v in self._jobs.items() if v.finished_at and now - v.finished_at > JOB_KEEP_SECONDS]:
            self._jobs.pop(jid, None)

    # --- étape : démontage de toutes les partitions -------------------------------------------------------------
    async def _unmount_all(self, job: FormatJob, disk: DiskInfo) -> DiskInfo:
        self._step(job, "unmount", "running")
        await asyncio.to_thread(os.sync)
        for attempt in range(UNMOUNT_TRIES):
            self._check_cancel(job)
            current = await self._fresh(disk)
            mounted = [p for p in current.partitions if p.mounted]
            if not mounted:
                self._step(job, "unmount", "ok")
                return current
            for part in mounted:
                try:
                    await self.svc.driver.unmount_device(part.path)
                except DeviceError as exc:
                    if exc.code != "busy" or attempt + 1 == UNMOUNT_TRIES:
                        if exc.code == "busy":
                            raise FormatRefusal("format_busy_mounted") from exc
                        raise
            await asyncio.sleep(UNMOUNT_PAUSE if attempt else 0.4)
        raise FormatRefusal("format_busy_mounted")

    async def _fresh(self, disk: DiskInfo) -> DiskInfo:
        """Le même disque, relu dans l'inventaire courant (par chemin ET identité)."""
        for candidate in await self.svc.driver.disks():
            if hardware_identity(candidate) == hardware_identity(disk):
                return candidate
        raise FormatRefusal("format_identity_changed")

    # --- étape : dernier examen avant le point de non-retour ------------------------------------------------------
    async def _recheck(self, job: FormatJob, planned: DiskInfo, support: dict[str, Any]) -> DiskInfo:
        self._step(job, "recheck", "running")
        self._check_cancel(job)
        disks = await self.svc.driver.disks()
        current = next((d for d in disks if d.path == planned.path), None)
        ctx = await self._context(current, support, ignore_job=job)
        refusal = self._refusal(evaluate(ctx), current)
        if refusal is not None:
            raise refusal
        assert current is not None
        # Les partitions peuvent avoir changé d'état de montage (le bureau remonte un support démonté) mais jamais d'identité.
        if fingerprint(current) != fingerprint(planned):
            raise FormatRefusal("format_identity_changed")
        if current.mountpoints:
            for part in current.partitions:
                if part.mounted:
                    await self.svc.driver.unmount_device(part.path)
            current = await self._fresh(current)
            if current.mountpoints:
                raise FormatRefusal("format_busy_mounted")
        self._check_cancel(job)
        self._step(job, "recheck", "ok")
        return current

    # --- étapes : effacement (point de non-retour) ---------------------------------------------------------------
    async def _erase_and_format(self, job: FormatJob, disk: DiskInfo, spec: FormatSpec) -> None:
        job.point_of_no_return = True            # À partir d'ici : plus d'annulation
        self._step(job, "table", "running")
        await self.svc.driver.create_partition_table(disk)
        await asyncio.sleep(0.8)
        self._step(job, "table", "ok")
        self._step(job, "format", "running")
        job.error = None
        await self.svc.driver.create_partition_and_format(await self._fresh(disk), spec)
        self._step(job, "format", "ok")

    # --- cascade de vérification après coup --------------------------------------------------------------------
    async def _wait_new_disk(self, disk: DiskInfo, spec: FormatSpec) -> DiskInfo | None:
        deadline = time.monotonic() + SETTLE_SECONDS
        while time.monotonic() < deadline:
            for candidate in await self.svc.driver.disks():
                if candidate.path == disk.path:
                    if hardware_identity(candidate) != hardware_identity(disk):
                        raise FormatRefusal("format_identity_changed")
                    parts = [p for p in candidate.partitions if p.fstype]
                    if parts and parts[0].uuid:
                        return candidate
            await asyncio.sleep(0.5)
        return None

    async def _wait_volume(self, device: str) -> Volume | None:
        deadline = time.monotonic() + SETTLE_SECONDS
        while time.monotonic() < deadline:
            await self.svc.refresh()
            vol = next((v for v in self.svc._by_key.values() if v.device == device), None)
            if vol is not None:
                return vol
            await asyncio.sleep(0.6)
        return None

    async def _verify(self, job: FormatJob, planned: DiskInfo, spec: FormatSpec, old_uuids: set[str], support: dict[str, Any]) -> dict[str, Any]:
        checks: list[dict[str, Any]] = []

        def add(cid: str, ok: bool, **detail: Any) -> None:
            checks.append({"id": cid, "ok": ok, **detail})

        # --- 1. relecture : type, étiquette, UUID nouveau, capacité, table, alignement
        self._step(job, "settle", "running")
        disk = await self._wait_new_disk(planned, spec)
        if disk is None:
            self._step(job, "settle", "failed")
            raise FormatRefusal("format_failed", "Le système n'a pas présenté le nouveau système de fichiers à temps.")
        self._step(job, "settle", "ok")
        self._step(job, "readback", "running")
        parts = [p for p in disk.partitions if not p.whole_disk]
        main = next((p for p in parts if p.fstype), None)
        add("table", disk.ptable == "gpt" and len(parts) == 1, table=disk.ptable, partitions=len(parts))
        if main is None:
            add("filesystem", False)
            self._step(job, "readback", "failed")
            return {"ok": False, "checks": checks}
        add("filesystem", (main.fstype or "").lower() == spec.fs, fstype=main.fstype)
        want_label = spec.label.upper() if spec.fs == "vfat" else spec.label
        add("label", (main.label or "") == want_label, label=main.label)
        add("uuid", bool(main.uuid) and main.uuid.lower() not in old_uuids, new=bool(main.uuid))
        add("capacity", main.size_bytes >= planned.size_bytes - 4 * ALIGNMENT, size_bytes=main.size_bytes)
        aligned = main.start_sectors is not None and (main.start_sectors * SECTOR) % ALIGNMENT == 0
        add("alignment", aligned if main.start_sectors is not None else True, start_sectors=main.start_sectors,
            known=main.start_sectors is not None)
        readback_ok = all(c["ok"] for c in checks)
        self._step(job, "readback", "ok" if readback_ok else "warn")

        # --- 2. remontage en lecture seule, puis phase d'écriture temporaire explicite, puis retour en lecture seule
        volume = await self._wait_volume(main.path)
        final_ro: bool | None = None
        write_info: dict[str, Any] = {}
        if volume is None:
            add("mount_ro", False, reason="not_listed")
            for step in ("mount_ro", "write_test", "back_ro"):
                self._step(job, step, "skipped")
        else:
            vkey = volume.key
            self._step(job, "mount_ro", "running")
            try:
                await self.svc.mount(vkey, "ro", _format_job=job.id)
                volume = self.svc._by_key.get(vkey) or volume
                add("mount_ro", volume.mounted and volume.mounted_read_only is True)
                self._step(job, "mount_ro", "ok" if checks[-1]["ok"] else "warn")
            except DeviceError as exc:
                add("mount_ro", False, reason=exc.code)
                self._step(job, "mount_ro", "failed")
            self._step(job, "write_test", "running")
            try:
                await self.svc.mount(vkey, "rw", _format_job=job.id)               # phase explicitement en lecture-écriture, temporaire
                volume = self.svc._by_key.get(vkey) or volume
                if volume.mountpoint:
                    write_info = await asyncio.to_thread(write_read_delete_test, volume.mountpoint)
                    add("write_test", bool(write_info.get("ok")), **{k: v for k, v in write_info.items() if k != "ok"})
                else:
                    add("write_test", False, reason="not_mounted")
                self._step(job, "write_test", "ok" if checks[-1]["ok"] else "warn")
            except DeviceError as exc:
                add("write_test", False, reason=exc.code)
                self._step(job, "write_test", "failed")
            self._step(job, "back_ro", "running")
            try:
                await self.svc.mount(vkey, "ro", _format_job=job.id)
                volume = self.svc._by_key.get(vkey) or volume
                final_ro = bool(volume.mounted and volume.mounted_read_only is True)
            except DeviceError as exc:
                final_ro = False
                add("back_read_only", False, reason=exc.code)
            else:
                add("back_read_only", final_ro)
            self._step(job, "back_ro", "ok" if final_ro else "warn")

        # --- 3. santé relue (SMART si possible) ; jamais bloquant
        self._step(job, "health", "running")
        health: dict[str, Any] = {"available": False, "reason": "unknown"}
        if volume is not None:
            try:
                report = await self.svc.driver.smart(volume)
                health = {"available": bool(report.get("available")), "status": report.get("status"), "reason": report.get("reason"),
                          "warnings": report.get("warnings", [])}
            except DeviceError as exc:
                health = {"available": False, "reason": exc.code}
        self._step(job, "health", "ok" if health.get("available") else "skipped")
        ok = all(c["ok"] for c in checks) and not (health.get("available") and health.get("status") in ("warning", "critical"))
        return {
            "ok": ok, "checks": checks, "filesystem": spec.fs, "label": want_label, "uuid_changed": bool(main.uuid and main.uuid.lower() not in old_uuids),
            "size_bytes": main.size_bytes, "mounted_read_only": final_ro, "health": health,
            "params": {k: v for k, v in write_info.items() if k in ("cluster_bytes", "reserved_blocks", "free_bytes")},
            "mkfs_args": list(spec.mkfs_args),
        }

    # ------------------------------------------------------------------ annulation et suivi
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


def write_read_delete_test(root: str) -> dict[str, Any]:
    """Écrit un petit fichier aléatoire, force l'écriture, le relit depuis le support (cache purgé), compare les empreintes,
    le supprime et vérifie qu'il a disparu. Mesure aussi la taille de cluster et les blocs réservés (statvfs)."""
    name = f".bobine-format-check-{secrets.token_hex(6)}"
    path = os.path.join(root, name)
    data = secrets.token_bytes(TEST_FILE_BYTES)
    expected = hashlib.sha256(data).hexdigest()
    info: dict[str, Any] = {"ok": False, "bytes": len(data)}
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(fd, data)
            os.fsync(fd)
            try:
                os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
            except (AttributeError, OSError):
                pass
        finally:
            os.close(fd)
        with open(path, "rb") as handle:
            try:
                os.posix_fadvise(handle.fileno(), 0, 0, os.POSIX_FADV_DONTNEED)
            except (AttributeError, OSError):
                pass
            actual = hashlib.sha256(handle.read()).hexdigest()
        info["hash_ok"] = actual == expected
        os.unlink(path)
        dir_fd = os.open(root, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
        info["deleted"] = not os.path.exists(path)
        stat = os.statvfs(root)
        info["cluster_bytes"] = stat.f_frsize
        info["reserved_blocks"] = max(0, stat.f_bfree - stat.f_bavail)
        info["free_bytes"] = stat.f_bavail * stat.f_frsize
        info["ok"] = bool(info["hash_ok"] and info["deleted"])
    except OSError as exc:
        info["error"] = exc.errno
        try:
            os.unlink(path)
        except OSError:
            pass
    return info
