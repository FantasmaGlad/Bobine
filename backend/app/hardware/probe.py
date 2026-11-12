"""Socle des sondes : heure de démarrage, présence d'une commande, propriétés Android, cache des identités matérielles."""
import logging

import os
import shutil
import subprocess
import sys
import time
from typing import Any

from app.utils.android_runtime import is_android

logger = logging.getLogger(__name__)

_SERVICE_START_TIME = time.time()

_HARDWARE_CACHE: dict[str, Any] = {
    "cpu_name": None,
    "gpu_name": None,
    "storage_model": None,
    "ram_info": None,
}


def shutil_which(cmd: str) -> bool:
    """Vérifie si une commande existe dans PATH sans lever d'exception."""
    try:
        return shutil.which(cmd) is not None
    except Exception:
        return False


def is_android_system() -> bool:
    """Détecte si l'environnement d'exécution est Android (Chaquopy ou shell Android Linux)."""
    return is_android() or (sys.platform.startswith("linux") and shutil_which("getprop"))


def _get_android_prop(prop_name: str) -> str:
    if shutil_which("getprop"):
        try:
            out = subprocess.check_output(["getprop", prop_name], text=True, timeout=1).strip()
            if out:
                return out
        except Exception as exc:
            logger.debug("_get_android_prop : %s", exc)

    for build_prop in ("/system/build.prop", "/default.prop", "/vendor/build.prop"):
        if os.path.exists(build_prop):
            try:
                with open(build_prop, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if line.startswith(f"{prop_name}="):
                            return line.split("=", 1)[1].strip()
            except Exception as exc:
                logger.debug("_get_android_prop : %s", exc)
    return ""
