import platform

from ..platforms import first_answer
from ..probe import _HARDWARE_CACHE
from . import android, linux, macos, windows

_IMPLEMENTATIONS = {"android": android, "linux": linux, "macos": macos, "windows": windows}


def get_cpu_model_name() -> str:
    """Nom commercial du processeur (ex. AMD Ryzen 7 8840U, Apple M1 Pro, Qualcomm Snapdragon 8 Elite)."""
    if _HARDWARE_CACHE["cpu_name"]:
        return _HARDWARE_CACHE["cpu_name"]
    name = first_answer(_IMPLEMENTATIONS, lambda implementation: implementation.cpu_name()) or platform.machine() or "CPU Inconnu"
    _HARDWARE_CACHE["cpu_name"] = name
    return name
