import glob
import os
import re

from ..probe import _get_android_prop, shutil_which
from .common import output, probe, read_text

_KGSL = "/sys/class/kgsl/kgsl-3d0"
_GPU_ZONES = ("gpu-0", "gpu-1", "gpu0", "gpuss", "gpu")


def _adreno_name() -> str | None:
    raw = read_text(f"{_KGSL}/gpu_model") if os.path.exists(f"{_KGSL}/gpu_model") else ""
    if not raw:
        return None
    match = re.match(r"([A-Za-z]+)(\d+)", raw)
    return f"Qualcomm {match.group(1)} {match.group(2)}" if match else f"Qualcomm {raw}"


def _surfaceflinger_name() -> str | None:
    if not shutil_which("dumpsys"):
        return None
    for line in output(["dumpsys", "SurfaceFlinger"]).splitlines():
        if "GLES:" in line:
            parts = line.split("GLES:", 1)[1].split(",")
            if len(parts) >= 2:
                return f"{parts[0].strip()} {parts[1].strip().replace('(TM)', '').strip()}"
    return None


def _egl_name() -> str | None:
    egl = _get_android_prop("ro.hardware.egl").strip()
    return f"Qualcomm {egl.capitalize()}" if egl else None


def _zone_temperature(zone: str) -> float | None:
    type_file, temp_file = os.path.join(zone, "type"), os.path.join(zone, "temp")
    if not (os.path.exists(type_file) and os.path.exists(temp_file)):
        return None
    if not any(key in read_text(type_file).lower() for key in _GPU_ZONES):
        return None
    value = int(read_text(temp_file))
    celsius = value / 1000.0 if value > 1000 else float(value)
    return round(celsius, 1) if 15.0 <= celsius <= 115.0 else None


def temperature() -> float | None:
    return next((t for zone in glob.glob("/sys/class/thermal/thermal_zone*")
                 if (t := probe(lambda zone=zone: _zone_temperature(zone))) is not None), None)


def busy_percent() -> float | None:
    if not os.path.exists(f"{_KGSL}/gpubusy"):
        return None
    values = read_text(f"{_KGSL}/gpubusy").split()
    if len(values) < 2 or int(values[1]) <= 0:
        return None
    return round(int(values[0]) / int(values[1]) * 100.0, 1)


def name() -> str | None:
    return next((value for value in (probe(read) for read in (_adreno_name, _surfaceflinger_name, _egl_name)) if value), None)
