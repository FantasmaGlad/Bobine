"""Pilote de stockage factice : simule branchements, montages et arrachages sans matériel ni root.

Chaque « disque » vit dans `<racine>/disks/<uuid>/` ; un montage est un lien symbolique `<racine>/mnt/<nom>` vers ce dossier
(un autre nom à chaque montage : le point de montage change d'un branchement à l'autre, comme sur un vrai système)."""

from __future__ import annotations

import dataclasses
import os
import shutil
from pathlib import Path
from typing import Any

from app.devices.base import DeviceError
from app.storage.drivers.base import StorageDriver
from app.storage.health import unavailable
from app.storage.types import Inventory, Volume, make_key


class FakeStorageDriver(StorageDriver):
    name = "fake"
    push_active = False

    def __init__(self, base: Path) -> None:
        super().__init__()
        self.base = base
        (base / "disks").mkdir(parents=True, exist_ok=True)
        (base / "mnt").mkdir(parents=True, exist_ok=True)
        self.volumes: dict[str, Volume] = {}
        self.mount_calls: list[tuple[str, list[str]]] = []
        self.unmount_calls: list[str] = []
        self.power_off_calls: list[str] = []
        self.fail_mount: DeviceError | None = None
        self.busy_on_unmount = False
        self.smart_report: dict[str, Any] = unavailable("permission", "Droits insuffisants")
        self.portable: dict[str, Any] = {"supported": False, "reason": "missing_tool", "install": "sudo apt install gvfs-backends gvfs-fuse", "devices": []}
        self._counter = 0
        self.root_user = False
        self.standby_calls: list[str] = []

    # --- scénarios -----------------------------------------------------------------------------------------
    def plug(self, name: str, uuid: str | None, files: dict[str, bytes] | None = None, *, fstype: str = "exfat", kind: str = "usb",
             label: str | None = None, mounted_rw: bool = False, rotational: bool | None = None, size: int = 64 * 10**9) -> Volume:
        disk = self.base / "disks" / (uuid or name)
        disk.mkdir(parents=True, exist_ok=True)
        for rel, data in (files or {}).items():
            target = disk / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        key = make_key(uuid, name, None, "1", size)
        if key in self.volumes:  # clone (même UUID) : clé distincte, comme `dedupe_keys` côté réel
            key = f"{key}-{name}1"
        vol = Volume(
            key=key, device=f"/dev/{name}1", name=f"{name}1", fs_uuid=uuid, label=label or name.upper(),
            fstype=fstype, size_bytes=size, mountpoint=None, removable=True, hotplug=True, transport="usb", kind=kind, dev_type="part",
            rotational=rotational, disk=name, discard_supported=kind in ("usb", "ssd"),
        )
        self.volumes[vol.key] = vol
        if mounted_rw:
            self._mount_state(vol.key, ["rw"])
        self._emit("volumes")
        return self.volumes[vol.key]

    def unplug(self, key: str) -> None:
        """Arrachage brutal : le volume disparaît de l'inventaire, le lien de montage devient orphelin."""
        vol = self.volumes.pop(key)
        if vol.mountpoint:
            try:
                os.remove(vol.mountpoint)
            except OSError:
                pass
            # Le dossier du disque reste, mais plus rien n'y mène : les chemins du montage sont morts.
        self._emit("volumes")

    def disk_dir(self, key: str) -> Path:
        vol = self.volumes[key]
        return self.base / "disks" / (vol.fs_uuid or vol.disk)

    def _mount_state(self, key: str, options: list[str]) -> str:
        vol = self.volumes[key]
        self._counter += 1
        mountpoint = self.base / "mnt" / f"{vol.label}-{self._counter}"
        os.symlink(self.base / "disks" / (vol.fs_uuid or vol.disk), mountpoint)
        self.volumes[key] = dataclasses.replace(vol, mountpoint=str(mountpoint), mounts=(str(mountpoint),), mount_options=tuple(options))
        return str(mountpoint)

    # --- pilote ------------------------------------------------------------------------------------------------
    async def capabilities(self) -> dict[str, dict[str, Any]]:
        return {k: {"supported": True} for k in ("inventory", "push_events", "mount", "eject", "smart", "trim", "standby", "portable")}

    async def inventory(self, protected_paths: list[str]) -> Inventory:
        return Inventory(volumes=list(self.volumes.values()))

    async def mount(self, volume: Volume, options: list[str]) -> str:
        self.mount_calls.append((volume.key, list(options)))
        if self.fail_mount:
            raise self.fail_mount
        if volume.key not in self.volumes:
            raise DeviceError("device_removed", "Le support a été retiré.", 404)
        if self.volumes[volume.key].mountpoint:
            raise DeviceError("already_mounted", "déjà monté", 409)
        return self._mount_state(volume.key, options)

    async def unmount(self, volume: Volume) -> None:
        if self.busy_on_unmount:
            raise DeviceError("busy", "occupé", 409)
        self.unmount_calls.append(volume.key)
        current = self.volumes.get(volume.key)
        if current and current.mountpoint:
            try:
                os.remove(current.mountpoint)
            except OSError:
                pass
            self.volumes[volume.key] = dataclasses.replace(current, mountpoint=None, mounts=(), mount_options=())

    async def power_off(self, volume: Volume) -> bool:
        self.power_off_calls.append(volume.key)
        self.volumes.pop(volume.key, None)
        return True

    async def smart(self, volume: Volume) -> dict[str, Any]:
        return self.smart_report

    async def standby(self, volume: Volume) -> str:
        self.standby_calls.append(volume.key)
        return "udisks"

    async def trim(self, volume: Volume) -> str:
        if not self.root_user:
            raise DeviceError("needs_root", "TRIM exige les droits d'administrateur.", 501)
        return "ok"

    async def facts(self) -> dict[str, Any]:
        return {"is_root": self.root_user, "fstrim_timer_enabled": True, "standby_supported": True}

    async def portable_status(self) -> dict[str, Any]:
        return self.portable


def make_volume_tree(root: Path, files: dict[str, bytes]) -> None:
    for rel, data in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


def clean(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)
