from ..platforms import first_answer
from ..probe import _HARDWARE_CACHE
from . import android, linux, macos, windows

_IMPLEMENTATIONS = {"android": android, "linux": linux, "macos": macos, "windows": windows}


def get_storage_model() -> str:
    """Modèle matériel du disque principal (SSD, NVMe, UFS, eMMC)."""
    if _HARDWARE_CACHE["storage_model"]:
        return _HARDWARE_CACHE["storage_model"]
    model = first_answer(_IMPLEMENTATIONS, lambda implementation: implementation.storage_model()) or "Stockage Système"
    _HARDWARE_CACHE["storage_model"] = model
    return model
