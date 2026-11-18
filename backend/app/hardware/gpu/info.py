from ..platforms import detected, first_answer
from ..probe import _HARDWARE_CACHE, shutil_which
from . import android, drm, fallback, macos, nvidia, sensors, windows
from .common import probe

_NAMES = {"macos": macos, "windows": windows}


def _nvidia_fill(name, percent, temp):
    nv_percent, nv_temp, nv_name = probe(nvidia.read) or (None, None, None)
    return name or nv_name, nv_percent if percent is None else percent, nv_temp if temp is None else temp


def get_gpu_info() -> tuple[str, float | None, float | None]:
    """Retourne (gpu_name, gpu_percent, gpu_temp_c)."""
    name = _HARDWARE_CACHE["gpu_name"]
    percent: float | None = None
    temp: float | None = None
    if "android" in detected():
        name = name or android.name()
        temp = android.temperature()
        percent = probe(android.busy_percent)
    if percent is None:
        percent = drm.busy_percent()
    if (percent is None or not name) and shutil_which("nvidia-smi"):
        name, percent, temp = _nvidia_fill(name, percent, temp)
    if temp is None:
        temp = probe(sensors.temperature)
    name = name or first_answer(_NAMES, lambda implementation: probe(implementation.name)) or fallback.name()
    _HARDWARE_CACHE["gpu_name"] = name
    return name, percent, temp
