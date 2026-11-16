"""Téléphones et tablettes par GVFS (MTP, PTP) : détection USB, montage, démontage."""

from __future__ import annotations

import asyncio
import os
import shutil
from typing import Any
from app.storage import portable
from ..base import DeviceError
from app.devices.linux.command import CommandResult


class PortableMixin:
    def _gvfs_env_dir(self) -> str:
        runtime = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{self._unix_uid}"
        return os.path.join(runtime, "gvfs")

    async def _gio(self, *args: str, timeout: float = 20.0) -> CommandResult:
        return await self._run("gio", *args, timeout=timeout)

    def _usb_candidates(self) -> list[portable.PortableDevice]:
        base = "/sys/bus/usb/devices"
        devices: list[dict[str, Any]] = []
        try:
            names = os.listdir(base)
        except OSError:
            return []

        def read(path: str) -> str | None:
            try:
                with open(path, encoding="utf-8", errors="replace") as handle:
                    return handle.read().strip()
            except OSError:
                return None

        for name in names:
            if ":" in name or name.startswith("usb"):
                continue
            path = os.path.join(base, name)
            interfaces = []
            for itf in sorted(os.listdir(path)):
                if not itf.startswith(name + ":"):
                    continue
                ipath = os.path.join(path, itf)
                interfaces.append({
                    "class": read(os.path.join(ipath, "bInterfaceClass")),
                    "subclass": read(os.path.join(ipath, "bInterfaceSubClass")),
                    "protocol": read(os.path.join(ipath, "bInterfaceProtocol")),
                    "name": read(os.path.join(ipath, "interface")),
                })
            devices.append({
                "busnum": read(os.path.join(path, "busnum")), "devnum": read(os.path.join(path, "devnum")),
                "idVendor": read(os.path.join(path, "idVendor")), "idProduct": read(os.path.join(path, "idProduct")),
                "product": read(os.path.join(path, "product")), "manufacturer": read(os.path.join(path, "manufacturer")),
                "interfaces": interfaces,
            })
        return portable.parse_sysfs_usb(devices)

    async def portable_status(self) -> dict[str, Any]:
        usb = await asyncio.to_thread(self._usb_candidates)
        if shutil.which("gio") is None:
            devices = [portable.PortableDevice(d.id, d.name, d.scheme, None, "missing_tool", d.bus, d.dev) for d in usb]
            return {
                "supported": False,
                "reason": "missing_tool",
                "install": portable.INSTALL_HELP["mtp"],
                "devices": [d.as_dict() for d in devices],
            }
        try:
            code, out, _ = await self._gio("mount", "-li", timeout=10.0)
        except DeviceError:
            code, out = 1, ""
        gvfs = portable.parse_gio_mounts(out) if code == 0 else []
        merged = portable.merge(gvfs, usb)
        return {"supported": True, "reason": None, "install": None, "devices": [d.as_dict() for d in merged]}

    async def _portable_find(self, device_id: str) -> portable.PortableDevice | None:
        try:
            code, out, _ = await self._gio("mount", "-li", timeout=10.0)
        except DeviceError:
            return None
        for dev in portable.parse_gio_mounts(out) if code == 0 else []:
            if dev.id == device_id:
                return dev
        return None

    async def portable_mount(self, device_id: str) -> dict[str, Any]:
        if shutil.which("gio") is None:
            raise DeviceError("missing_tool", "GVFS n'est pas installé : " + portable.INSTALL_HELP["mtp"], 501)
        dev = await self._portable_find(device_id)
        if dev is None or not dev.uri:
            raise DeviceError("not_ready", "L'appareil n'est pas encore proposé par le système : déverrouillez-le et choisissez « Transfert de fichiers ».", 409)
        if dev.state != "mounted":
            code, out, err = await self._gio("mount", dev.uri, timeout=40.0)
            if code != 0 and "already" not in err.lower():
                state, hint = portable.classify_mount_error(err)
                raise DeviceError(state, portable.HINT_MESSAGES.get(hint, "L'appareil n'est pas prêt."), 409)
        root = await asyncio.to_thread(portable.fuse_root_for, dev.uri, self._gvfs_env_dir())
        if root is None:
            raise DeviceError("fuse_missing", "Le dossier de l'appareil n'est pas exposé (paquet gvfs-fuse manquant ?).", 501)
        return {"root": root, "id": dev.id}

    async def portable_unmount(self, device_id: str) -> None:
        dev = await self._portable_find(device_id)
        if dev is None or not dev.uri:
            return
        await self._gio("mount", "-u", dev.uri, timeout=30.0)

    def portable_root(self, device_id: str) -> str | None:
        return None

