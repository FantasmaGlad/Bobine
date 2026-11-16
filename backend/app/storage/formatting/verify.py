"""Vérification après formatage : relecture, montage, test d'écriture, santé."""

from __future__ import annotations

import asyncio
import hashlib
import os
import secrets
from typing import Any
from app.devices.base import DeviceError
from .model import DiskInfo, FormatSpec
from .options import (
    ALIGNMENT,
)
from .refusals import FormatRefusal
from .job import FormatJob, _Checks, _wanted_label


TEST_FILE_BYTES = 64 * 1024


SECTOR = 512


def write_read_delete_test(root: str) -> dict[str, Any]:
    """Écrit un petit fichier aléatoire, force l'écriture, le relit depuis le support (cache purgé), compare les empreintes, le supprime et vérifie qu'il a disparu."""
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


class VerifyMixin:
    def _readback(self, job: FormatJob, disk: DiskInfo, planned: DiskInfo, spec: FormatSpec, old_uuids: set[str], checks: "_Checks"):
        self._step(job, "readback", "running")
        parts = [p for p in disk.partitions if not p.whole_disk]
        main = next((p for p in parts if p.fstype), None)
        checks.add("table", disk.ptable == "gpt" and len(parts) == 1, table=disk.ptable, partitions=len(parts))
        if main is None:
            checks.add("filesystem", False)
            self._step(job, "readback", "failed")
            return None
        checks.add("filesystem", (main.fstype or "").lower() == spec.fs, fstype=main.fstype)
        checks.add("label", (main.label or "") == _wanted_label(spec), label=main.label)
        checks.add("uuid", bool(main.uuid) and main.uuid.lower() not in old_uuids, new=bool(main.uuid))
        checks.add("capacity", main.size_bytes >= planned.size_bytes - 4 * ALIGNMENT, size_bytes=main.size_bytes)
        known = main.start_sectors is not None
        checks.add("alignment", (main.start_sectors * SECTOR) % ALIGNMENT == 0 if known else True,
                   start_sectors=main.start_sectors, known=known)
        self._step(job, "readback", "ok" if checks.all_ok() else "warn")
        return main

    async def _mount_step(self, job: FormatJob, step: str, check: str, vkey: str, mode: str, volume, checks: "_Checks", probe):
        self._step(job, step, "running")
        try:
            await self.svc.mount(vkey, mode, _format_job=job.id)
            volume = self.svc._by_key.get(vkey) or volume
            await probe(volume)
            self._step(job, step, "ok" if checks.last_ok() else "warn")
        except DeviceError as exc:
            checks.add(check, False, reason=exc.code)
            self._step(job, step, "failed")
        return volume

    async def _mount_checks(self, job: FormatJob, volume, checks: "_Checks") -> tuple[Any, bool | None, dict[str, Any]]:
        if volume is None:
            checks.add("mount_ro", False, reason="not_listed")
            for step in ("mount_ro", "write_test", "back_ro"):
                self._step(job, step, "skipped")
            return None, None, {}
        vkey = volume.key
        write_info: dict[str, Any] = {}

        async def read_only(v) -> None:
            checks.add("mount_ro", v.mounted and v.mounted_read_only is True)

        async def write_test(v) -> None:
            if not v.mountpoint:
                checks.add("write_test", False, reason="not_mounted")
                return
            write_info.update(await asyncio.to_thread(write_read_delete_test, v.mountpoint))
            checks.add("write_test", bool(write_info.get("ok")), **{k: val for k, val in write_info.items() if k != "ok"})

        volume = await self._mount_step(job, "mount_ro", "mount_ro", vkey, "ro", volume, checks, read_only)
        volume = await self._mount_step(job, "write_test", "write_test", vkey, "rw", volume, checks, write_test)
        self._step(job, "back_ro", "running")
        try:
            await self.svc.mount(vkey, "ro", _format_job=job.id)
            volume = self.svc._by_key.get(vkey) or volume
            final_ro = bool(volume.mounted and volume.mounted_read_only is True)
            checks.add("back_read_only", final_ro)
        except DeviceError as exc:
            final_ro = False
            checks.add("back_read_only", False, reason=exc.code)
        self._step(job, "back_ro", "ok" if final_ro else "warn")
        return volume, final_ro, write_info

    async def _health_after_format(self, job: FormatJob, volume) -> dict[str, Any]:
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
        return health

    async def _verify(self, job: FormatJob, planned: DiskInfo, spec: FormatSpec, old_uuids: set[str], support: dict[str, Any]) -> dict[str, Any]:
        checks = _Checks()
        self._step(job, "settle", "running")
        disk = await self._wait_new_disk(planned, spec)
        if disk is None:
            self._step(job, "settle", "failed")
            raise FormatRefusal("format_failed", "Le système n'a pas présenté le nouveau système de fichiers à temps.")
        self._step(job, "settle", "ok")
        main = self._readback(job, disk, planned, spec, old_uuids, checks)
        if main is None:
            return {"ok": False, "checks": checks.items}
        volume, final_ro, write_info = await self._mount_checks(job, await self._wait_volume(main.path), checks)
        health = await self._health_after_format(job, volume)
        ok = checks.all_ok() and not (health.get("available") and health.get("status") in ("warning", "critical"))
        return {
            "ok": ok, "checks": checks.items, "filesystem": spec.fs, "label": _wanted_label(spec),
            "uuid_changed": bool(main.uuid and main.uuid.lower() not in old_uuids),
            "size_bytes": main.size_bytes, "mounted_read_only": final_ro, "health": health,
            "params": {k: v for k, v in write_info.items() if k in ("cluster_bytes", "reserved_blocks", "free_bytes")},
            "mkfs_args": list(spec.mkfs_args),
        }

