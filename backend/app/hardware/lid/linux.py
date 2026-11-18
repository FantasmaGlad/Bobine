import shutil
import subprocess
from pathlib import Path

from .common import COMMAND_TIMEOUT_SECONDS, has_battery, logger

_GNOME_POWER = "org.gnome.settings-daemon.plugins.power"


def has_lid() -> bool:
    lid_proc = Path("/proc/acpi/button/lid")
    if lid_proc.exists():
        try:
            if any(lid_proc.iterdir()):
                return True
        except Exception as exc:
            logger.debug("_has_laptop_lid : %s", exc)
    return has_battery()


def prevent_sleep() -> bool:
    if not shutil.which("gsettings"):
        return False
    try:
        res = subprocess.run(
            ["gsettings", "get", _GNOME_POWER, "lid-close-ac-action"],
            capture_output=True,
            text=True,
            check=False,
            timeout=COMMAND_TIMEOUT_SECONDS,
        )
        if res.returncode == 0:
            return "nothing" in res.stdout
    except Exception as e:
        logger.debug(f"Erreur lecture gsettings capot Linux : {e}")
    return False


def set_prevent_sleep(prevent: bool) -> bool:
    if not shutil.which("gsettings"):
        return False
    try:
        action = "nothing" if prevent else "suspend"
        res = subprocess.run(
            ["gsettings", "set", _GNOME_POWER, "lid-close-ac-action", action],
            capture_output=True,
            text=True,
            check=False,
            timeout=COMMAND_TIMEOUT_SECONDS,
        )
        return res.returncode == 0
    except Exception as e:
        logger.error(f"Erreur écriture gsettings capot Linux : {e}")
        return False
