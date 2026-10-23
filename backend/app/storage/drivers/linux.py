"""Pilote Linux : `lsblk` (inventaire), `udisksctl`/udisks2 (montage sans privilèges), `smartctl`, GVFS.

* **Inventaire** : `lsblk -J -b` (une commande, ~10 ms) + `/proc/self/mountinfo` (options de montage) ;
  **déclencheur** : signaux D-Bus udisks2 (`InterfacesAdded/Removed`, `PropertiesChanged`) via `dbus-fast`,
  avec interrogation périodique de secours (le service la règle selon que les signaux fonctionnent).
* **Actions** : `udisksctl` (polkit, jamais sudo) ; le `runner` est injectable pour les tests.
* Aucun appel ne lève d'exception brute : `DeviceError` (code stable) ou rapport `unavailable`.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
import logging
import os
import re
import shutil
import time
from typing import Any, Awaitable, Callable

from app.devices.linux import run_command
from app.storage import health, portable
from app.storage.formatting.disks import DISK_COLUMNS, DISK_COLUMNS_FALLBACK, parse_disks
from app.storage.formatting.model import DiskInfo, FormatSpec
from app.storage.formatting.options import SPECS
from app.storage.lsblk import LSBLK_COLUMNS, parse_lsblk, parse_mountinfo
from app.storage.types import Inventory, Volume

from .base import CAPABILITY_KEYS, DeviceError, StorageDriver

logger = logging.getLogger(__name__)

CommandResult = tuple[int, str, str]
Runner = Callable[..., Awaitable[CommandResult]]

_UDISKS = "org.freedesktop.UDisks2"
_UDISKS_ROOT = "/org/freedesktop/UDisks2"
FORMAT_TIMEOUT = 300.0
_PROBE_TTL = 30.0
_MOUNTED_AT = re.compile(r"[Mm]ounted .+? at (.+?)\.?\s*$", re.M)
_ALREADY_AT = re.compile(r"already mounted at [`'\"]?(.+?)['\"]?\.?\s*$", re.M)


def _stderr(text: str) -> str:
    return text.strip().splitlines()[-1] if text.strip() else ""


def classify_udisks_error(message: str) -> tuple[str, int, str]:
    """(code stable, statut HTTP, message lisible) d'une erreur `udisksctl`."""
    low = message.lower()
    if "optionnotpermitted" in low or "is not allowed" in low:
        return "option_not_permitted", 400, "Le système refuse une option de montage demandée."
    if "notauthorized" in low or "not authorized" in low or "authentication" in low:
        return "not_authorized", 403, "Le système refuse cette opération (autorisation polkit manquante pour ce compte)."
    if "target is busy" in low or "device or resource busy" in low or "busy" in low:
        return "busy", 409, "Le support est en cours d'utilisation : arrêtez la lecture ou l'import, puis réessayez."
    if any(w in low for w in ("unclean", "hibernated", "dirty", "inconsistent", "wrong fs type", "bad superblock", "mount failed: unknown")):
        return "dirty", 409, "Le système de fichiers semble endommagé ou n'a pas été fermé proprement : réparez-le (fsck, ou le brancher sur Windows/macOS) avant de l'utiliser."
    if "not a mountable filesystem" in low or "unknown filesystem" in low or "no filesystem" in low:
        return "unsupported_fs", 400, "Ce système de fichiers n'est pas pris en charge par le système."
    if "notmounted" in low or "not mounted" in low:
        return "not_mounted", 409, "Le support n'est pas monté."
    if "no such" in low or "not found" in low or "no object" in low:
        return "device_removed", 404, "Le support a été retiré."
    return "mount_failed", 502, "Le système n'a pas pu exécuter cette opération."


def classify_dbus_error(name: str, message: str) -> DeviceError:
    """Erreur D-Bus de udisks2 -> erreur structurée (le texte brut, qui contient des chemins système, reste dans le journal)."""
    logger.info("udisks2 : %s %s", name, message)
    low = (name + " " + message).lower()
    if "notauthorized" in low or "not authorized" in low or "authentication" in low:
        return DeviceError("format_not_authorized", "Le système refuse cette opération (autorisation polkit manquante pour ce compte).", 403)
    if "devicebusy" in low or "busy" in low:
        return DeviceError("format_busy_mounted", "Le support est encore utilisé par un autre programme : fermez-le puis recommencez.", 409)
    if "notsupported" in low or "not supported" in low or "no such" in low and "program" in low:
        return DeviceError("format_tool_missing", "Un composant du système manque pour formater (outil de ce format).", 501)
    if "optionnotpermitted" in low:
        return DeviceError("option_not_permitted", "Le système refuse une option de formatage.", 400)
    return DeviceError("format_failed", "Le système n'a pas pu exécuter le formatage.", 502)


class LinuxStorageDriver(StorageDriver):
    name = "linux"

    def __init__(self, runner: Runner = run_command, *, sys_block: str = "/sys/block", mountinfo_path: str = "/proc/self/mountinfo") -> None:
        super().__init__()
        self._run = runner
        self._sys_block = sys_block
        self._mountinfo_path = mountinfo_path
        self._bus: Any = None
        self._watch_task: asyncio.Task[None] | None = None
        self.push_active = False
        self._probe_cache: tuple[float, dict[str, dict[str, Any]]] | None = None
        self._facts_cache: tuple[float, dict[str, Any]] | None = None
        self._unix_uid = os.getuid() if hasattr(os, "getuid") else 0

    # ------------------------------------------------------------------ cycle de vie
    async def start(self) -> None:
        if self._watch_task is None or self._watch_task.done():
            self._watch_task = asyncio.create_task(self._watch_udisks())

    async def stop(self) -> None:
        task, self._watch_task = self._watch_task, None
        if task is not None and not task.done():
            task.cancel()
        bus, self._bus = self._bus, None
        if bus is not None:
            try:
                bus.disconnect()
            except Exception:
                pass
        self.push_active = False

    async def _watch_udisks(self) -> None:
        """Abonnement aux signaux udisks2 : un branchement ou un retrait est signalé sans attendre l'interrogation."""
        try:
            from dbus_fast import BusType, Message, MessageType
            from dbus_fast.aio import MessageBus
        except ImportError:
            return
        while True:
            try:
                bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
                self._bus = bus

                def handler(message: Any) -> None:
                    if message.message_type == MessageType.SIGNAL and (message.path or "").startswith("/org/freedesktop/UDisks2"):
                        if message.member in ("InterfacesAdded", "InterfacesRemoved", "PropertiesChanged"):
                            self._emit("volumes")

                bus.add_message_handler(handler)
                for member, iface, path_kw in (
                    ("InterfacesAdded", "org.freedesktop.DBus.ObjectManager", "path"),
                    ("InterfacesRemoved", "org.freedesktop.DBus.ObjectManager", "path"),
                    ("PropertiesChanged", "org.freedesktop.DBus.Properties", "path_namespace"),
                ):
                    rule = f"type='signal',sender='{_UDISKS}',interface='{iface}',member='{member}'," + (
                        "path='/org/freedesktop/UDisks2'" if path_kw == "path" else "path_namespace='/org/freedesktop/UDisks2'"
                    )
                    await bus.call(
                        Message(
                            destination="org.freedesktop.DBus", path="/org/freedesktop/DBus", interface="org.freedesktop.DBus",
                            member="AddMatch", signature="s", body=[rule],
                        )
                    )
                self.push_active = True
                await bus.wait_for_disconnect()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.debug("Surveillance udisks2 indisponible : %s", exc)
            self.push_active = False
            await asyncio.sleep(30)

    # ------------------------------------------------------------------ capacités
    async def capabilities(self) -> dict[str, dict[str, Any]]:
        now = time.monotonic()
        if self._probe_cache and now - self._probe_cache[0] < _PROBE_TTL:
            return self._probe_cache[1]
        caps: dict[str, dict[str, Any]] = {k: {"supported": False, "reason": ""} for k in CAPABILITY_KEYS}
        have_lsblk = shutil.which("lsblk") is not None
        caps["inventory"] = {"supported": have_lsblk} if have_lsblk else {"supported": False, "reason": "L'outil lsblk (util-linux) n'est pas installé."}

        udisks_reason = await self._probe_udisks()
        for key in ("mount", "eject"):
            caps[key] = {"supported": udisks_reason is None}
            if udisks_reason:
                caps[key]["reason"] = udisks_reason
        caps["push_events"] = {"supported": self.push_active}
        if not self.push_active:
            caps["push_events"]["reason"] = "Interrogation périodique légère (udisks2 ne signale pas les changements)."

        caps["smart"] = {"supported": True} if shutil.which("smartctl") else {"supported": False, "reason": "L'outil smartctl (paquet smartmontools) n'est pas installé."}
        facts = await self.facts()
        if facts["is_root"] and shutil.which("fstrim"):
            caps["trim"] = {"supported": True}
        else:
            caps["trim"] = {"supported": False, "reason": "TRIM exige les droits d'administrateur : le minuteur fstrim du système s'en charge" if shutil.which("fstrim") else "L'outil fstrim n'est pas installé."}
        caps["standby"] = {"supported": facts["standby_supported"]}
        if not facts["standby_supported"]:
            caps["standby"]["reason"] = "Aucun moyen de mettre un disque en veille sans droits (udisks2 ou hdparm requis)."
        fmt = await self.format_support()
        caps["format"] = {"supported": fmt["supported"]}
        if not fmt["supported"]:
            caps["format"]["reason"] = fmt["reason"]
        portable_ok = shutil.which("gio") is not None
        caps["portable"] = {"supported": portable_ok}
        if not portable_ok:
            caps["portable"]["reason"] = "GVFS n'est pas installé : " + portable.INSTALL_HELP["mtp"]
        self._probe_cache = (now, caps)
        return caps

    async def _probe_udisks(self) -> str | None:
        if shutil.which("udisksctl") is None:
            return "udisks2 n'est pas installé (paquet udisks2) : les supports sont listés mais ne peuvent pas être montés ici."
        try:
            code, _, err = await self._run("udisksctl", "status", timeout=5.0)
        except DeviceError as exc:
            return exc.message
        if code != 0:
            return "Le service udisks2 ne répond pas : " + _stderr(err)
        return None

    async def facts(self) -> dict[str, Any]:
        now = time.monotonic()
        if self._facts_cache and now - self._facts_cache[0] < _PROBE_TTL:
            return self._facts_cache[1]
        is_root = hasattr(os, "geteuid") and os.geteuid() == 0
        timer: bool | None = None
        if shutil.which("systemctl"):
            try:
                code, out, _ = await self._run("systemctl", "is-enabled", "fstrim.timer", timeout=4.0)
                timer = out.strip() == "enabled" if code in (0, 1) else None
            except DeviceError:
                timer = None
        standby = is_root and shutil.which("hdparm") is not None or (shutil.which("busctl") is not None and shutil.which("udisksctl") is not None)
        facts = {"is_root": is_root, "fstrim_timer_enabled": timer, "standby_supported": bool(standby)}
        self._facts_cache = (now, facts)
        return facts

    # ------------------------------------------------------------------ inventaire
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

    async def inventory(self, protected_paths: list[str]) -> Inventory:
        try:
            code, out, err = await self._run("lsblk", "-J", "-b", "-o", LSBLK_COLUMNS, timeout=8.0)
            if code != 0 or not out.strip():
                # Anciennes versions d'util-linux : colonnes en moins (jamais celles qui servent à écarter les disques système).
                code, out, err = await self._run("lsblk", "-J", "-b", "-o", LSBLK_COLUMNS.replace(",DISC-GRAN", "").replace(",PARTN", ""), timeout=8.0)
        except DeviceError:
            raise
        if code != 0 or not out.strip():
            raise DeviceError("inventory_failed", "Impossible de lister les supports : " + _stderr(err), 502)
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

    # ------------------------------------------------------------------ montage
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
        code, out, err = await self._run("udisksctl", "unmount", "-b", volume.device, "--no-user-interaction", timeout=60.0)
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

    # ------------------------------------------------------------------ santé, veille, TRIM
    async def smart(self, volume: Volume) -> dict[str, Any]:
        if not volume.disk:
            return health.unavailable("no_smart")
        if shutil.which("smartctl") is None:
            return health.unavailable("tool_missing", "L'outil smartctl (paquet smartmontools) n'est pas installé.")
        device = f"/dev/{volume.disk}"
        report = await self._smartctl(device, [])
        if not report["available"] and report["reason"] == "no_smart" and volume.transport == "usb":
            retry = await self._smartctl(device, ["-d", "sat"])  # pont USB-SATA
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
        if mounted_ro := volume.mounted_read_only:
            raise DeviceError("read_only", "Le support est monté en lecture seule : TRIM n'a rien à faire.", 409)
        code, out, err = await self._run("fstrim", "-v", volume.mountpoint, timeout=300.0)
        if code != 0:
            raise DeviceError("trim_failed", "TRIM a échoué : " + _stderr(err), 502)
        return out.strip()

    # ------------------------------------------------------------------ formatage (udisks2, sans privilèges)
    async def _udisks_call(self, path: str, interface: str, member: str, signature: str, body: list[Any], *, timeout: float = FORMAT_TIMEOUT) -> Any:
        """Appel D-Bus de udisks2 (dbus-fast) ; une erreur devient un `DeviceError` à code stable, jamais une exception brute."""
        try:
            from dbus_fast import BusType, Message, MessageType
            from dbus_fast.aio import MessageBus
        except ImportError as exc:
            raise DeviceError("format_tool_missing", "Le composant D-Bus (dbus-fast) est absent.", 501) from exc
        bus = None
        try:
            bus = await asyncio.wait_for(MessageBus(bus_type=BusType.SYSTEM).connect(), timeout=10.0)
            reply = await asyncio.wait_for(
                bus.call(Message(destination=_UDISKS, path=path, interface=interface, member=member, signature=signature, body=body)),
                timeout=timeout,
            )
        except asyncio.TimeoutError as exc:
            raise DeviceError("format_failed", "Le système n'a pas répondu à temps.", 504) from exc
        except Exception as exc:  # noqa: BLE001 - tout échec de bus devient une erreur structurée
            if isinstance(exc, DeviceError):
                raise
            raise DeviceError("format_failed", "Le service udisks2 est injoignable.", 502) from exc
        finally:
            if bus is not None:
                try:
                    bus.disconnect()
                except Exception:  # noqa: BLE001
                    pass
        if reply.message_type == MessageType.ERROR:
            raise classify_dbus_error(reply.error_name or "", str(reply.body[0]) if reply.body else "")
        return reply.body

    async def disks(self) -> list[DiskInfo]:
        try:
            code, out, err = await self._run("lsblk", "-J", "-b", "-o", DISK_COLUMNS, timeout=8.0)
            if code != 0 or not out.strip():
                code, out, err = await self._run("lsblk", "-J", "-b", "-o", DISK_COLUMNS_FALLBACK, timeout=8.0)
        except DeviceError:
            raise
        if code != 0 or not out.strip():
            raise DeviceError("inventory_failed", "Impossible de lister les disques : " + _stderr(err), 502)
        try:
            disks = parse_disks(out, is_sd_card=self._is_sd)
            result = []
            for disk in disks:
                try:
                    with open(f"/sys/class/block/{disk.name}/diskseq", encoding="ascii") as handle:
                        sequence = handle.read().strip()
                except OSError:
                    sequence = None
                result.append(replace(disk, diskseq=sequence))
            return result
        except (ValueError, KeyError, TypeError) as exc:
            raise DeviceError("inventory_failed", f"Réponse lsblk illisible : {exc}", 502) from exc

    async def format_support(self) -> dict[str, Any]:
        tools = {fs: any(shutil.which(t) for t in spec.tools) for fs, spec in SPECS.items()}
        reason = await self._probe_udisks()
        if reason is None:
            try:
                import dbus_fast  # noqa: F401
            except ImportError:
                reason = "Le composant D-Bus (dbus-fast) est absent."
        if reason is None and not shutil.which("lsblk"):
            reason = "L'outil lsblk (util-linux) n'est pas installé."
        return {"supported": reason is None and any(tools.values()), "reason": reason, "tools": tools}

    async def unmount_device(self, device_path: str) -> None:
        code, out, err = await self._run("udisksctl", "unmount", "-b", device_path, "--no-user-interaction", timeout=60.0)
        if code != 0:
            text = (out + "\n" + err).strip()
            if "NotMounted" in text:
                return
            error_code, status, message = classify_udisks_error(text)
            raise DeviceError(error_code, message, status)

    @staticmethod
    def _block_path(disk_path: str) -> str:
        return f"{_UDISKS_ROOT}/block_devices/{os.path.basename(disk_path)}"

    async def create_partition_table(self, disk: DiskInfo) -> None:
        await self._udisks_call(self._block_path(disk.path), "org.freedesktop.UDisks2.Block", "Format", "sa{sv}", ["gpt", {}])

    async def create_partition_and_format(self, disk: DiskInfo, spec: FormatSpec) -> str:
        from dbus_fast import Variant

        options: dict[str, Any] = {"auth.no_user_interaction": Variant("b", True), "label": Variant("s", spec.label), "mkfs-args": Variant("as", list(spec.mkfs_args))}
        if spec.take_ownership:
            options["take-ownership"] = Variant("b", True)
        body = await self._udisks_call(
            self._block_path(disk.path), "org.freedesktop.UDisks2.PartitionTable", "CreatePartitionAndFormat", "ttssa{sv}sa{sv}",
            [spec.offset_bytes, 0, spec.partition_guid, spec.partition_name, {}, spec.udisks_type, options],
        )
        created = str(body[0]) if body else ""
        name = created.rsplit("/", 1)[-1]
        if not name:
            raise DeviceError("format_failed", "La partition créée n'a pas pu être identifiée.", 502)
        return f"/dev/{name}"

    async def wipe_disk(self, disk: DiskInfo) -> None:
        await self._udisks_call(self._block_path(disk.path), "org.freedesktop.UDisks2.Block", "Format", "sa{sv}", ["empty", {}])

    # ------------------------------------------------------------------ appareils portables (GVFS)
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
        return None  # résolu par le service à partir de `portable_mount` (racine mémorisée)
