"""Inventaire lsblk, montage et démontage sans privilèges, mise hors tension."""

from __future__ import annotations

import asyncio
import os
import re
from app.storage.lsblk import LSBLK_COLUMNS, parse_lsblk, parse_mountinfo
from app.storage.types import Inventory, Volume
from ..base import DeviceError
from .errors import _stderr, classify_udisks_error


_MOUNTED_AT = re.compile(r"[Mm]ounted .+? at (.+?)\.?\s*$", re.M)


_ALREADY_AT = re.compile(r"already mounted at [`'\"]?(.+?)['\"]?\.?\s*$", re.M)


class InventoryMixin:
    def _is_sd(self, disk: str) -> bool:
        try:
            with open(os.path.join(self._sys_block, disk, "device", "type"), encoding="utf-8") as handle:
                return handle.read().strip().upper() == "SD"
        except OSError:
            return False

    def _read_mountinfo(self) -> str:
        try:
            with open(self._mountinfo_path, encoding="utf-8", errors="replace") as handle:
                return handle.read()
        except OSError:
            return ""

    async def _lsblk(self, columns: str, fallback: str, what: str) -> str:
        code, out, err = await self._run("lsblk", "-J", "-b", "-o", columns, timeout=8.0)
        if code != 0 or not out.strip():
            code, out, err = await self._run("lsblk", "-J", "-b", "-o", fallback, timeout=8.0)
        if code != 0 or not out.strip():
            raise DeviceError("inventory_failed", f"Impossible de lister {what} : " + _stderr(err), 502)
        return out

    async def inventory(self, protected_paths: list[str]) -> Inventory:
        out = await self._lsblk(LSBLK_COLUMNS, LSBLK_COLUMNS.replace(",DISC-GRAN", "").replace(",PARTN", ""), "les supports")
        mountinfo = await asyncio.to_thread(self._read_mountinfo)
        try:
            return parse_lsblk(
                out,
                mountinfo=parse_mountinfo(mountinfo),
                protected_paths=protected_paths,
                is_sd_card=self._is_sd,
            )
        except (ValueError, KeyError, TypeError) as exc:
            raise DeviceError("inventory_failed", f"Réponse lsblk illisible : {exc}", 502) from exc

    async def mount(self, volume: Volume, options: list[str]) -> str:
        code, out, err = await self._run(
            "udisksctl", "mount", "-b", volume.device, "-o", ",".join(options), "--no-user-interaction", timeout=45.0
        )
        text = (out + "\n" + err).strip()
        if code != 0:
            already = _ALREADY_AT.search(text)
            if already and "AlreadyMounted" in text:
                return already.group(1)
            error_code, status, message = classify_udisks_error(text)
            raise DeviceError(error_code, message, status)
        match = _MOUNTED_AT.search(text)
        if not match:
            raise DeviceError("mount_failed", "Le point de montage n'a pas pu être déterminé.", 502)
        return match.group(1)

    async def unmount(self, volume: Volume) -> None:
        await self.unmount_device(volume.device)

    async def unmount_device(self, device_path: str) -> None:
        code, out, err = await self._run("udisksctl", "unmount", "-b", device_path, "--no-user-interaction", timeout=60.0)
        if code != 0:
            text = (out + "\n" + err).strip()
            if "NotMounted" in text:
                return
            error_code, status, message = classify_udisks_error(text)
            raise DeviceError(error_code, message, status)

    async def power_off(self, volume: Volume) -> bool:
        """Extinction du disque parent (USB) ; une image disque n'a rien à éteindre (on libère le périphérique loop)."""
        if volume.dev_type == "loop":
            code, out, err = await self._run("udisksctl", "loop-delete", "-b", volume.device, "--no-user-interaction", timeout=20.0)
            return code == 0
        if not volume.disk or volume.sd_card:
            return False
        code, out, err = await self._run("udisksctl", "power-off", "-b", f"/dev/{volume.disk}", "--no-user-interaction", timeout=30.0)
        if code != 0:
            error_code, status, message = classify_udisks_error(out + "\n" + err)
            if error_code in ("busy", "not_authorized"):
                raise DeviceError(error_code, message, status)
            return False
        return True

