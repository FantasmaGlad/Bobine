"""Carte graphique : nom, charge, température."""
import logging

import glob
import os
import re
import subprocess
import sys
from typing import Callable

import psutil

from .cpu import get_cpu_model_name
from .probe import _HARDWARE_CACHE, _get_android_prop, is_android_system, shutil_which

logger = logging.getLogger(__name__)

_KGSL = "/sys/class/kgsl/kgsl-3d0"
_GPU_ZONES = ("gpu-0", "gpu-1", "gpu0", "gpuss", "gpu")
_VIRTUAL_ADAPTERS = ("virtual", "remote", "rdp", "basic display")
_DISPLAY_CLASSES = ("vga compatible controller", "3d controller", "display controller")


def _probe(read: Callable[[], object]):
    try:
        return read()
    except Exception as exc:
        logger.debug("get_gpu_info : %s", exc)
        return None


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read().strip()


def _output(command: list[str], timeout: float = 1) -> str:
    return subprocess.check_output(command, text=True, timeout=timeout)


def _adreno_name() -> str | None:
    raw = _read(f"{_KGSL}/gpu_model") if os.path.exists(f"{_KGSL}/gpu_model") else ""
    if not raw:
        return None
    match = re.match(r"([A-Za-z]+)(\d+)", raw)
    return f"Qualcomm {match.group(1)} {match.group(2)}" if match else f"Qualcomm {raw}"


def _surfaceflinger_name() -> str | None:
    if not shutil_which("dumpsys"):
        return None
    for line in _output(["dumpsys", "SurfaceFlinger"]).splitlines():
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
    if not any(key in _read(type_file).lower() for key in _GPU_ZONES):
        return None
    value = int(_read(temp_file))
    celsius = value / 1000.0 if value > 1000 else float(value)
    return round(celsius, 1) if 15.0 <= celsius <= 115.0 else None


def _android_temperature() -> float | None:
    return next((t for zone in glob.glob("/sys/class/thermal/thermal_zone*")
                 if (t := _probe(lambda zone=zone: _zone_temperature(zone))) is not None), None)


def _kgsl_busy() -> float | None:
    if not os.path.exists(f"{_KGSL}/gpubusy"):
        return None
    values = _read(f"{_KGSL}/gpubusy").split()
    if len(values) < 2 or int(values[1]) <= 0:
        return None
    return round(int(values[0]) / int(values[1]) * 100.0, 1)


def _drm_busy() -> float | None:
    for path in glob.glob("/sys/class/drm/card*/device/gpu_busy_percent"):
        value = _probe(lambda path=path: _read(path))
        if value and value.isdigit():
            return float(value)
    return None


def _nvidia() -> tuple[float | None, float | None, str | None]:
    fields = "--query-gpu=utilization.gpu,temperature.gpu,name"
    parts = [p.strip() for p in _output(["nvidia-smi", fields, "--format=csv,noheader,nounits"]).strip().splitlines()[0].split(",")]
    if len(parts) < 2:
        return None, None, None
    return float(parts[0]), float(parts[1]), parts[2] if len(parts) >= 3 else None


def _sensor_temperature() -> float | None:
    temps = psutil.sensors_temperatures() or {}
    return next((round(temps[k][0].current, 1) for k in ("amdgpu", "nouveau", "nvidia") if temps.get(k)), None)


def _macos_name() -> str | None:
    for line in _output(["system_profiler", "SPDisplaysDataType"], 2).splitlines():
        if line.strip().startswith("Chipset Model:"):
            return line.split(":", 1)[1].strip()
    return None


def _windows_name() -> str | None:
    out = _output(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_VideoController).Name"], 2)
    names = [line.strip() for line in out.splitlines() if line.strip()]
    return next((n for n in names if not any(x in n.lower() for x in _VIRTUAL_ADAPTERS)), None)


def _apu_name(cpu_model: str) -> str | None:
    if "w/" not in cpu_model:
        return None
    name = cpu_model.split("w/", 1)[1].strip()
    return f"AMD {name}" if not name.startswith("AMD ") and "Radeon" in name else name or None


def _lspci_label(raw: str) -> str:
    start, end = raw.find("["), raw.find("]", raw.find("["))
    if start < 0 or end < 0:
        return raw.split("(")[0].strip()
    label = raw[start + 1:end].strip()
    if not label:
        return raw.split("(")[0].strip()
    return f"Intel {label}" if "Intel" in raw and not label.lower().startswith("intel") else label


def _lspci_name() -> str | None:
    if not shutil_which("lspci"):
        return None
    for line in _output(["lspci"]).splitlines():
        if any(kind in line.lower() for kind in _DISPLAY_CLASSES):
            return _lspci_label(line.split(":", 2)[-1].strip())
    return None


def _first(*probes: Callable[[], str | None]) -> str | None:
    for probe in probes:
        value = _probe(probe)
        if value:
            return value
    return None


def _fallback_name() -> str:
    cpu_model = get_cpu_model_name()
    name = _apu_name(cpu_model) or _probe(_lspci_name)
    if name:
        return name
    return "Intel HD/UHD Graphics" if "Intel" in cpu_model else "GPU Inconnu"


def get_gpu_info() -> tuple[str, float | None, float | None]:
    """Retourne (gpu_name, gpu_percent, gpu_temp_c)."""
    name = _HARDWARE_CACHE["gpu_name"]
    percent: float | None = None
    temp: float | None = None
    if is_android_system():
        name = name or _first(_adreno_name, _surfaceflinger_name, _egl_name)
        temp = _android_temperature()
        percent = _probe(_kgsl_busy)
    if percent is None:
        percent = _drm_busy()
    if (percent is None or not name) and shutil_which("nvidia-smi"):
        nv_percent, nv_temp, nv_name = _probe(_nvidia) or (None, None, None)
        percent = nv_percent if percent is None else percent
        temp = nv_temp if temp is None else temp
        name = name or nv_name
    if temp is None:
        temp = _probe(_sensor_temperature)
    if not name and sys.platform == "darwin":
        name = _probe(_macos_name)
    if not name and sys.platform == "win32":
        name = _probe(_windows_name)
    name = name or _fallback_name()
    _HARDWARE_CACHE["gpu_name"] = name
    return name, percent, temp
