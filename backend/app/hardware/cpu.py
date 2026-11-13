"""Processeur : nom commercial, température, charge lissée."""
import logging

import glob
import os
import platform
import subprocess
import sys
import time

import psutil

from .probe import _HARDWARE_CACHE, _get_android_prop, is_android_system

logger = logging.getLogger(__name__)

_LAST_CPU_TIMES: tuple[float, float, float] = (0.0, 0.0, 0.0)
_LAST_SMOOTH_CPU_PCT: float = 0.0


_SOC_NAME_MAP: dict[str, str] = {
    "SM8750": "Qualcomm Snapdragon 8 Elite",
    "SM8735": "Qualcomm Snapdragon 8 Elite",
    "SM8735P": "Qualcomm Snapdragon 8 Elite",
    "SUN": "Qualcomm Snapdragon 8 Elite",
    "SM8650": "Qualcomm Snapdragon 8 Gen 3",
    "PINEAPPLE": "Qualcomm Snapdragon 8 Gen 3",
    "SM8635": "Qualcomm Snapdragon 8s Gen 3",
    "CLITI": "Qualcomm Snapdragon 8s Gen 3",
    "SM8550": "Qualcomm Snapdragon 8 Gen 2",
    "KALAMA": "Qualcomm Snapdragon 8 Gen 2",
    "SM8475": "Qualcomm Snapdragon 8+ Gen 1",
    "CAPE": "Qualcomm Snapdragon 8+ Gen 1",
    "SM8450": "Qualcomm Snapdragon 8 Gen 1",
    "TARO": "Qualcomm Snapdragon 8 Gen 1",
    "SM8350": "Qualcomm Snapdragon 888",
    "LAHAINA": "Qualcomm Snapdragon 888",
    "SM8250": "Qualcomm Snapdragon 865",
    "KONA": "Qualcomm Snapdragon 865",
    "SM8150": "Qualcomm Snapdragon 855",
    "SM7675": "Qualcomm Snapdragon 7+ Gen 3",
    "SM7550": "Qualcomm Snapdragon 7 Gen 3",
    "SM7475": "Qualcomm Snapdragon 7+ Gen 2",
    "SM7450": "Qualcomm Snapdragon 7 Gen 1",
    "SM7325": "Qualcomm Snapdragon 778G",
    "SM7250": "Qualcomm Snapdragon 765G",
    "SM6450": "Qualcomm Snapdragon 6 Gen 1",
    "SM6375": "Qualcomm Snapdragon 695",
    "SM4450": "Qualcomm Snapdragon 4 Gen 2",
    "TENSOR G4": "Google Tensor G4",
    "ZUMA PRO": "Google Tensor G4",
    "TENSOR G3": "Google Tensor G3",
    "ZUMA": "Google Tensor G3",
    "TENSOR G2": "Google Tensor G2",
    "CLOUDRIPPER": "Google Tensor G2",
    "TENSOR": "Google Tensor G1",
    "WHITECAP": "Google Tensor G1",
    "MT6991": "MediaTek Dimensity 9400",
    "MT6989": "MediaTek Dimensity 9300",
    "MT6985": "MediaTek Dimensity 9200",
    "MT6983": "MediaTek Dimensity 9000",
    "MT6897": "MediaTek Dimensity 8300",
    "MT6895": "MediaTek Dimensity 8100",
}


def _soc_file(name: str) -> str:
    path = f"/sys/devices/soc0/{name}"
    if not os.path.exists(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read().strip()
    except Exception as exc:
        logger.debug("get_cpu_model_name : %s", exc)
        return ""


def _android_cpu_name() -> str:
    soc_model = _get_android_prop("ro.soc.model").strip()
    platform_code = _get_android_prop("ro.board.platform").strip()
    family, machine = _soc_file("family"), _soc_file("machine")
    for candidate in (soc_model.upper(), platform_code.upper(), machine.upper()):
        if candidate in _SOC_NAME_MAP:
            return _SOC_NAME_MAP[candidate]
    if soc_model:
        if soc_model.upper().startswith("SM") or "SNAPDRAGON" in family.upper():
            return f"Qualcomm Snapdragon ({soc_model})"
        if soc_model.upper().startswith("MT"):
            return f"MediaTek Dimensity ({soc_model})"
        return f"SoC {soc_model}"
    return f"Qualcomm Snapdragon ({platform_code})" if platform_code else ""


def _cpuinfo_name() -> str:
    if not os.path.exists("/proc/cpuinfo"):
        return ""
    name = ""
    with open("/proc/cpuinfo", "r", encoding="utf-8") as handle:
        for line in handle:
            value = line.split(":", 1)[1].strip() if ":" in line else ""
            if "model name" in line and value:
                return value
            if ("Hardware" in line or "Processor" in line) and not name and value.lower() not in ("", "aarch64", "armv8", "armv7"):
                name = value
    return name


def _macos_cpu_name() -> str:
    return subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"], text=True).strip()


def _windows_cpu_name() -> str:
    import winreg
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
        value, _ = winreg.QueryValueEx(key, "ProcessorNameString")
    return str(value or "").strip() or platform.processor() or ""


def _guarded(read) -> str:
    try:
        return read()
    except Exception as exc:
        logger.debug("get_cpu_model_name : %s", exc)
        return ""


def get_cpu_model_name() -> str:
    """Retourne le nom commercial du processeur (ex: AMD Ryzen 7 8840U, Intel Celeron J4105, Apple M1 Pro, Qualcomm Snapdragon 8 Elite)."""
    if _HARDWARE_CACHE["cpu_name"]:
        return _HARDWARE_CACHE["cpu_name"]
    name = _android_cpu_name() if is_android_system() else ""
    if not name and sys.platform.startswith("linux"):
        name = _guarded(_cpuinfo_name)
    if not name and sys.platform == "darwin":
        name = _guarded(_macos_cpu_name)
    if not name and sys.platform == "win32":
        name = _guarded(_windows_cpu_name) or platform.processor() or ""
    name = name or platform.machine() or "CPU Inconnu"
    _HARDWARE_CACHE["cpu_name"] = name
    return name


def get_cpu_temp() -> float | None:
    """Retourne la température CPU principale en °C."""
    try:
        temps = psutil.sensors_temperatures()
        if temps:
            for key in ("k10temp", "coretemp", "cpu_thermal", "soc_thermal", "acpitz"):
                if key in temps and temps[key]:
                    for entry in temps[key]:
                        if 10.0 <= entry.current <= 125.0:
                            return round(entry.current, 1)
            for group in temps.values():
                for entry in group:
                    if 10.0 <= entry.current <= 125.0:
                        return round(entry.current, 1)
    except Exception as exc:
        logger.debug("get_cpu_temp : %s", exc)

    for p in glob.glob("/sys/class/thermal/thermal_zone*/temp"):
        try:
            with open(p, "r", encoding="utf-8") as f:
                val = int(f.read().strip())
                c = val / 1000.0 if val > 1000 else float(val)
                if 10.0 <= c <= 125.0:
                    return round(c, 1)
        except Exception as exc:
            logger.debug("get_cpu_temp : %s", exc)

    return None


def get_cpu_percent() -> float:
    """Calcule la charge CPU globale du système de manière non bloquante et lissée."""
    global _LAST_CPU_TIMES, _LAST_SMOOTH_CPU_PCT
    now = time.time()
    last_wall, last_total, last_idle = _LAST_CPU_TIMES

    if last_wall > 0 and (now - last_wall) < 1.5:
        return _LAST_SMOOTH_CPU_PCT

    if os.path.exists("/proc/stat"):
        try:
            with open("/proc/stat", "r", encoding="utf-8") as f:
                line = f.readline()
                if line.startswith("cpu "):
                    parts = [float(x) for x in line.split()[1:]]
                    idle = parts[3] + (parts[4] if len(parts) > 4 else 0.0)
                    total = sum(parts)
                    if last_wall > 0 and total > last_total:
                        delta_total = total - last_total
                        delta_idle = idle - last_idle
                        pct = (1.0 - (delta_idle / delta_total)) * 100.0
                        _LAST_SMOOTH_CPU_PCT = round(min(100.0, max(0.0, pct)), 1)
                    _LAST_CPU_TIMES = (now, total, idle)
                    return _LAST_SMOOTH_CPU_PCT
        except Exception as exc:
            logger.debug("get_cpu_percent : %s", exc)

    if os.path.exists("/proc/loadavg"):
        try:
            with open("/proc/loadavg", "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    load1 = float(content.split()[0])
                    cpu_count = os.cpu_count() or 1
                    pct = round(min(100.0, max(0.0, (load1 / cpu_count) * 100.0)), 1)
                    _LAST_SMOOTH_CPU_PCT = pct
                    _LAST_CPU_TIMES = (now, 0.0, 0.0)
                    return _LAST_SMOOTH_CPU_PCT
        except Exception as exc:
            logger.debug("get_cpu_percent : %s", exc)

    try:
        val = psutil.cpu_percent(interval=None)
        if val > 0.0:
            _LAST_SMOOTH_CPU_PCT = round(val, 1)
            _LAST_CPU_TIMES = (now, 0.0, 0.0)
            return _LAST_SMOOTH_CPU_PCT
    except Exception as exc:
        logger.debug("get_cpu_percent : %s", exc)

    if os.path.exists("/proc/self/stat"):
        try:
            with open("/proc/self/stat", "r", encoding="utf-8") as f:
                parts = f.read().split()
                utime = int(parts[13])
                stime = int(parts[14])
                total_ticks = utime + stime
            cpu_count = os.cpu_count() or 1
            clk_tck = os.sysconf(os.sysconf_names.get("SC_CLK_TCK", 100)) if hasattr(os, "sysconf") else 100
            if last_wall > 0 and now > last_wall and last_total > 0:
                delta_sec = now - last_wall
                delta_ticks = total_ticks - last_total
                if delta_sec > 0 and delta_ticks >= 0:
                    pct = (delta_ticks / clk_tck) / delta_sec / cpu_count * 100.0
                    _LAST_SMOOTH_CPU_PCT = round(min(100.0, max(0.0, pct)), 1)
            _LAST_CPU_TIMES = (now, total_ticks, 0.0)
            return _LAST_SMOOTH_CPU_PCT
        except Exception as exc:
            logger.debug("get_cpu_percent : %s", exc)

    _LAST_CPU_TIMES = (now, 0.0, 0.0)
    return _LAST_SMOOTH_CPU_PCT
