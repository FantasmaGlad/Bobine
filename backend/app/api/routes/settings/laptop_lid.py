"""Maintien de l'activité capot fermé sur un ordinateur portable."""

import logging
import shutil
import subprocess
import sys
from pathlib import Path

import psutil
from fastapi import (
    HTTPException,
)
from pydantic import BaseModel

from .core import router

logger = logging.getLogger(__name__)


class LaptopLidPayload(BaseModel):
    prevent_sleep: bool


def _has_laptop_lid() -> bool:
    if sys.platform == "win32":
        try:
            return psutil.sensors_battery() is not None
        except Exception:
            return False
    lid_proc = Path("/proc/acpi/button/lid")
    if lid_proc.exists():
        try:
            if any(lid_proc.iterdir()):
                return True
        except Exception:
            pass
    try:
        return psutil.sensors_battery() is not None
    except Exception:
        return False


def _get_lid_prevent_sleep() -> bool:
    if sys.platform == "win32":
        try:
            res = subprocess.run(
                ["powercfg", "/query", "SCHEME_CURRENT", "SUB_BUTTONS", "LIDACTION"],
                capture_output=True,
                text=True,
                check=False,
            )
            return "0x00000000" in res.stdout or " 0 " in res.stdout
        except Exception as e:
            logger.debug(f"Erreur lecture powercfg capot Windows : {e}")
            return False

    if shutil.which("gsettings"):
        try:
            res = subprocess.run(
                ["gsettings", "get", "org.gnome.settings-daemon.plugins.power", "lid-close-ac-action"],
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode == 0:
                return "nothing" in res.stdout
        except Exception as e:
            logger.debug(f"Erreur lecture gsettings capot Linux : {e}")

    return False


def _set_lid_prevent_sleep(prevent: bool) -> bool:
    if sys.platform == "win32":
        try:
            val = "0" if prevent else "1"
            subprocess.run(
                ["powercfg", "/setacvalueindex", "SCHEME_CURRENT", "SUB_BUTTONS", "LIDACTION", val],
                check=False,
            )
            subprocess.run(["powercfg", "/setactive", "SCHEME_CURRENT"], check=False)
            return True
        except Exception as e:
            logger.error(f"Erreur écriture powercfg capot Windows : {e}")
            return False

    if shutil.which("gsettings"):
        try:
            action = "nothing" if prevent else "suspend"
            res = subprocess.run(
                ["gsettings", "set", "org.gnome.settings-daemon.plugins.power", "lid-close-ac-action", action],
                capture_output=True,
                text=True,
                check=False,
            )
            return res.returncode == 0
        except Exception as e:
            logger.error(f"Erreur écriture gsettings capot Linux : {e}")
            return False

    return False


@router.get("/laptop-lid")
def get_laptop_lid():
    """Vérifie si la machine a un capot et renvoie le réglage actuel."""
    has_lid = _has_laptop_lid()
    prevent = _get_lid_prevent_sleep() if has_lid else False
    return {"has_lid": has_lid, "prevent_sleep": prevent}


@router.post("/laptop-lid")
def set_laptop_lid(payload: LaptopLidPayload):
    """Active ou désactive la mise en veille à la fermeture du capot."""
    if not _has_laptop_lid():
        raise HTTPException(status_code=400, detail="Aucun capot détecté sur cet appareil")
    success = _set_lid_prevent_sleep(payload.prevent_sleep)
    if not success:
        raise HTTPException(status_code=500, detail="Impossible d'appliquer le réglage du capot")
    return {"has_lid": True, "prevent_sleep": payload.prevent_sleep}
