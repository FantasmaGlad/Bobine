"""Stockage principal : modèle et occupation du dossier des médias."""
import logging

import glob
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from .probe import _HARDWARE_CACHE, _get_android_prop, is_android_system, shutil_which

logger = logging.getLogger(__name__)


def _android_storage_model() -> str:
    bootdevice = (_get_android_prop("ro.boot.bootdevice") or _get_android_prop("ro.boot.boot_devices")).lower()
    soc_model = _get_android_prop("ro.soc.model").upper()
    if "ufshc" in bootdevice:
        if any(s in soc_model for s in ("SM8750", "SM8735", "SUN", "SM8650", "PINEAPPLE")):
            return "Flash UFS 4.0 (256 Go)"
        if any(s in soc_model for s in ("SM8550", "KALAMA", "SM8475")):
            return "Flash UFS 3.1"
        return "Flash UFS"
    return "Flash eMMC 5.1" if "mmc" in bootdevice else ""


def _first_line(command: list[str], timeout: float, select=lambda line: line) -> str:
    """Première ligne utile de la sortie d'une commande ; vide si elle échoue."""
    try:
        out = subprocess.check_output(command, text=True, timeout=timeout)
    except Exception as exc:
        logger.debug("get_storage_model : %s", exc)
        return ""
    return next((value for value in (select(line) for line in out.splitlines()) if value), "")


def _linux_storage_model() -> str:
    for path in glob.glob("/sys/block/*/device/model"):
        if any(x in path for x in ("loop", "ram", "zram")):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                value = f.read().strip()
            if value:
                return value
        except Exception as exc:
            logger.debug("get_storage_model : %s", exc)
    if shutil_which("lsblk"):
        return _first_line(["lsblk", "-d", "-n", "-o", "MODEL"], 1, str.strip)
    return ""


def _macos_media_name(line: str) -> str:
    return line.split(":", 1)[1].strip() if "Device / Media Name:" in line else ""


def get_storage_model() -> str:
    """Retourne le modèle matériel du disque de stockage principal (SSD, NVMe, UFS, eMMC)."""
    if _HARDWARE_CACHE["storage_model"]:
        return _HARDWARE_CACHE["storage_model"]
    model = _android_storage_model() if is_android_system() else ""
    if not model and sys.platform.startswith("linux"):
        model = _linux_storage_model()
    if not model and sys.platform == "darwin":
        model = _first_line(["diskutil", "info", "/"], 2, _macos_media_name)
    if not model and sys.platform == "win32":
        model = _first_line(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_DiskDrive).Model"], 2, str.strip)
    model = model or "Stockage Système"
    _HARDWARE_CACHE["storage_model"] = model
    return model


def get_storage_usage() -> dict[str, Any]:
    """Mesure l'espace disque réel sur le dossier média applicatif (et non sur / qui est un ramdisk système de 700 Mo en lecture seule sous Android)."""
    try:
        from app.config import runtime_settings
        media_dir = Path(runtime_settings.media_dir)
    except Exception:
        media_dir = Path("data")

    probe = media_dir
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    if not probe.exists():
        probe = Path(".")

    try:
        usage = shutil.disk_usage(probe)
        used_pct = round((usage.used / usage.total) * 100, 1) if usage.total else 0.0
        return {
            "total_bytes": usage.total,
            "used_bytes": usage.used,
            "free_bytes": usage.free,
            "used_percent": used_pct,
        }
    except Exception:
        return {"total_bytes": 0, "used_bytes": 0, "free_bytes": 0, "used_percent": 0.0}
