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


def get_storage_model() -> str:
    """Retourne le modèle matériel du disque de stockage principal (SSD, NVMe, UFS, eMMC)."""
    if _HARDWARE_CACHE["storage_model"]:
        return _HARDWARE_CACHE["storage_model"]

    model = ""
    is_android = is_android_system()

    if is_android:
        bootdevice = _get_android_prop("ro.boot.bootdevice") or _get_android_prop("ro.boot.boot_devices")
        soc_model = _get_android_prop("ro.soc.model").upper()

        if "ufshc" in bootdevice.lower():
            if any(s in soc_model for s in ("SM8750", "SM8735", "SUN", "SM8650", "PINEAPPLE")):
                model = "Flash UFS 4.0 (256 Go)"
            elif any(s in soc_model for s in ("SM8550", "KALAMA", "SM8475")):
                model = "Flash UFS 3.1"
            else:
                model = "Flash UFS"
        elif "mmc" in bootdevice.lower():
            model = "Flash eMMC 5.1"

    if not model and sys.platform.startswith("linux"):
        for p in glob.glob("/sys/block/*/device/model"):
            if any(x in p for x in ("loop", "ram", "zram")):
                continue
            try:
                with open(p, "r", encoding="utf-8") as f:
                    val = f.read().strip()
                    if val:
                        model = val
                        break
            except Exception as exc:
                logger.debug("get_storage_model : %s", exc)

        if not model and shutil_which("lsblk"):
            try:
                out = subprocess.check_output(["lsblk", "-d", "-n", "-o", "MODEL"], text=True, timeout=1)
                for line in out.splitlines():
                    line = line.strip()
                    if line:
                        model = line
                        break
            except Exception as exc:
                logger.debug("get_storage_model : %s", exc)

    if not model and sys.platform == "darwin":
        try:
            out = subprocess.check_output(["diskutil", "info", "/"], text=True, timeout=2)
            for line in out.splitlines():
                if "Device / Media Name:" in line:
                    model = line.split(":", 1)[1].strip()
                    break
        except Exception as exc:
            logger.debug("get_storage_model : %s", exc)

    if not model and sys.platform == "win32":
        try:
            out = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_DiskDrive).Model"],
                text=True,
                timeout=2,
            )
            for line in out.splitlines():
                sline = line.strip()
                if sline:
                    model = sline
                    break
        except Exception as exc:
            logger.debug("get_storage_model : %s", exc)

    if not model:
        model = "Stockage Système"

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
