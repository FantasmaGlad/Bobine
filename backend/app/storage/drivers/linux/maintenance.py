"""SMART, mise en veille et TRIM des disques."""

from __future__ import annotations

import os
import shutil
from typing import Any
from app.storage import health
from app.storage.types import Volume
from ..base import DeviceError
from .errors import _stderr
from .udisks import _UDISKS


class MaintenanceMixin:
    async def smart(self, volume: Volume) -> dict[str, Any]:
        if not volume.disk:
            return health.unavailable("no_smart")
        if shutil.which("smartctl") is None:
            return health.unavailable("tool_missing", "L'outil smartctl (paquet smartmontools) n'est pas installé.")
        device = f"/dev/{volume.disk}"
        report = await self._smartctl(device, [])
        if not report["available"] and report["reason"] == "no_smart" and volume.transport == "usb":
            retry = await self._smartctl(device, ["-d", "sat"])
            if retry["available"] or retry["reason"] == "permission":
                report = retry
        return report

    async def _smartctl(self, device: str, extra: list[str]) -> dict[str, Any]:
        try:
            _, out, err = await self._run("smartctl", "-j", "-a", *extra, device, timeout=25.0)
        except DeviceError as exc:
            return health.unavailable("tool_missing" if exc.code == "tool_missing" else "no_smart", exc.message)
        if not out.strip():
            return health.unavailable("permission" if "permission" in err.lower() else "no_smart", _stderr(err) or None)
        return health.parse_smartctl(out)

    async def standby(self, volume: Volume) -> str:
        """Met le disque en veille : udisks2 (`PmStandby`, sans droits si polkit l'autorise) puis `hdparm -y` (root)."""
        if not volume.disk:
            raise DeviceError("standby_failed", "Disque inconnu.", 400)
        errors: list[str] = []
        if shutil.which("busctl"):
            try:
                code, out, err = await self._run(
                    "busctl", "--system", "get-property", _UDISKS, f"/org/freedesktop/UDisks2/block_devices/{volume.disk}",
                    "org.freedesktop.UDisks2.Block", "Drive", timeout=6.0,
                )
                drive = out.split('"')[1] if code == 0 and '"' in out else None
                if drive and drive != "/":
                    code, out, err = await self._run(
                        "busctl", "--system", "call", _UDISKS, drive, "org.freedesktop.UDisks2.Drive.Ata", "PmStandby", "a{sv}", "0", timeout=15.0
                    )
                    if code == 0:
                        return "udisks"
                    errors.append(_stderr(err))
            except DeviceError as exc:
                errors.append(exc.message)
        if hasattr(os, "geteuid") and os.geteuid() == 0 and shutil.which("hdparm"):
            code, out, err = await self._run("hdparm", "-y", f"/dev/{volume.disk}", timeout=15.0)
            if code == 0:
                return "hdparm"
            errors.append(_stderr(err))
        raise DeviceError("standby_failed", "Mise en veille impossible : " + ("; ".join(e for e in errors if e) or "droits insuffisants."), 502)

    async def trim(self, volume: Volume) -> str:
        if not volume.mountpoint:
            raise DeviceError("not_mounted", "Le support n'est pas monté.", 409)
        if not (hasattr(os, "geteuid") and os.geteuid() == 0):
            raise DeviceError("needs_root", "TRIM exige les droits d'administrateur ; le minuteur fstrim du système s'en charge.", 501)
        if volume.mounted_read_only:
            raise DeviceError("read_only", "Le support est monté en lecture seule : TRIM n'a rien à faire.", 409)
        code, out, err = await self._run("fstrim", "-v", volume.mountpoint, timeout=300.0)
        if code != 0:
            raise DeviceError("trim_failed", "TRIM a échoué : " + _stderr(err), 502)
        return out.strip()

