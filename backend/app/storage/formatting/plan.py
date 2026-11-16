"""Plan du formatage en lecture seule : garde, contexte, refus, contenu actuel et options."""

from __future__ import annotations

from app.storage.lsblk import media_for_kind
import asyncio
import logging
import os
from typing import Any
from app.devices.base import DeviceError
from app.storage import fsadvisor, library
from app.storage.types import Volume
from . import content as content_mod
from .model import DiskInfo, FormatSpec, fingerprint, inventory_digest
from .options import (
    ALIGNMENT, SPECS, SUPPORTED, confirm_expected, mkfs_args, option_for, partition_bytes_for,
)
from .refusals import FormatRefusal
from .rules import GuardContext, candidates, evaluate, first_refusal
from .job import FormatJob

logger = logging.getLogger(__name__)


OWN_ENV_IMAGES = "BOBINE_STORAGE_FORMAT_IMAGES"


OWN_ENV_ONLY = "BOBINE_STORAGE_FORMAT_ONLY"


def _env_allow_images() -> bool:
    return os.environ.get(OWN_ENV_IMAGES, "") == "1"


def _env_allowlist() -> frozenset[str] | None:
    raw = os.environ.get(OWN_ENV_ONLY, "").strip()
    return frozenset(p.strip() for p in raw.split(",") if p.strip()) if raw else None


class PlanMixin:
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
            except FileNotFoundError:
                continue
            except OSError as exc:
                logger.warning("Chemin protégé %s illisible, non comparé par périphérique : %s", path, exc)
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

    async def plan(self, key: str, *, owner: str, travels: list[str]) -> dict[str, Any]:
        support = await self.svc.driver.format_support()
        vol, disk, disks = await self._resolve(key)
        ctx = await self._context(disk, support)
        checks = evaluate(ctx)
        refusal = self._refusal(checks, disk)
        if refusal is not None:
            raise refusal
        assert disk is not None and vol is not None

        reads = await self._content_of(disk)
        _, disk, disks = await self._resolve(key)
        if disk is None:
            raise FormatRefusal("format_not_found")
        ctx = await self._context(disk, support)
        refusal = self._refusal(evaluate(ctx), disk)
        if refusal is not None:
            raise refusal

        others = tuple(o for o in travels if o in fsadvisor.OSES and o != "linux")
        media = media_for_kind(disk.kind)
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

    def _spec(self, fs: str, label: str, disk: DiskInfo) -> FormatSpec:
        spec = SPECS[fs]
        return FormatSpec(
            fs=fs, label=label, udisks_type=spec.udisks_type, partition_guid=spec.partition_guid, partition_name=label[:36],
            mkfs_args=tuple(mkfs_args(fs, partition_bytes_for(disk.size_bytes))), take_ownership=spec.take_ownership,
        )

