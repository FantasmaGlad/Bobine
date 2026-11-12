"""Processeur : nom commercial, température, charge lissée."""

import glob
import os
import platform
import subprocess
import sys
import time

import psutil

from .probe import _HARDWARE_CACHE, _get_android_prop, is_android_system

# État de lissage CPU non bloquant
_LAST_CPU_TIMES: tuple[float, float, float] = (0.0, 0.0, 0.0)  # (wall_time, total_ticks, idle_ticks)
_LAST_SMOOTH_CPU_PCT: float = 0.0


# Dictionnaire de correspondance commerciale des SoCs Qualcomm Snapdragon, MediaTek, Google Tensor et Samsung Exynos
_SOC_NAME_MAP: dict[str, str] = {
    # Qualcomm Snapdragon 8 Series
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
    # Qualcomm Snapdragon 7 Series
    "SM7675": "Qualcomm Snapdragon 7+ Gen 3",
    "SM7550": "Qualcomm Snapdragon 7 Gen 3",
    "SM7475": "Qualcomm Snapdragon 7+ Gen 2",
    "SM7450": "Qualcomm Snapdragon 7 Gen 1",
    "SM7325": "Qualcomm Snapdragon 778G",
    "SM7250": "Qualcomm Snapdragon 765G",
    # Qualcomm Snapdragon 6/4 Series
    "SM6450": "Qualcomm Snapdragon 6 Gen 1",
    "SM6375": "Qualcomm Snapdragon 695",
    "SM4450": "Qualcomm Snapdragon 4 Gen 2",
    # Google Tensor
    "TENSOR G4": "Google Tensor G4",
    "ZUMA PRO": "Google Tensor G4",
    "TENSOR G3": "Google Tensor G3",
    "ZUMA": "Google Tensor G3",
    "TENSOR G2": "Google Tensor G2",
    "CLOUDRIPPER": "Google Tensor G2",
    "TENSOR": "Google Tensor G1",
    "WHITECAP": "Google Tensor G1",
    # MediaTek Dimensity
    "MT6991": "MediaTek Dimensity 9400",
    "MT6989": "MediaTek Dimensity 9300",
    "MT6985": "MediaTek Dimensity 9200",
    "MT6983": "MediaTek Dimensity 9000",
    "MT6897": "MediaTek Dimensity 8300",
    "MT6895": "MediaTek Dimensity 8100",
}


def get_cpu_model_name() -> str:
    """
    Retourne le nom commercial du processeur (ex: AMD Ryzen 7 8840U, Intel Celeron J4105,
    Apple M1 Pro, Qualcomm Snapdragon 8 Elite).
    Prise en charge multi-OS : Linux (desktop/headless), macOS, Windows, Android.
    """
    if _HARDWARE_CACHE["cpu_name"]:
        return _HARDWARE_CACHE["cpu_name"]

    name = ""
    is_android = is_android_system()

    # 1. ANDROID : détection SoC via getprop et sysfs
    if is_android:
        soc_model = _get_android_prop("ro.soc.model").strip()
        platform_code = _get_android_prop("ro.board.platform").strip()

        # Lecture sysfs /sys/devices/soc0 si disponible
        soc_family = ""
        soc_machine = ""
        if os.path.exists("/sys/devices/soc0/family"):
            try:
                with open("/sys/devices/soc0/family", "r", encoding="utf-8") as f:
                    soc_family = f.read().strip()
            except Exception:
                pass
        if os.path.exists("/sys/devices/soc0/machine"):
            try:
                with open("/sys/devices/soc0/machine", "r", encoding="utf-8") as f:
                    soc_machine = f.read().strip()
            except Exception:
                pass

        for candidate in (soc_model.upper(), platform_code.upper(), soc_machine.upper()):
            if candidate in _SOC_NAME_MAP:
                name = _SOC_NAME_MAP[candidate]
                break

        if not name and soc_model:
            if soc_model.upper().startswith("SM") or "SNAPDRAGON" in soc_family.upper():
                name = f"Qualcomm Snapdragon ({soc_model})"
            elif soc_model.upper().startswith("MT"):
                name = f"MediaTek Dimensity ({soc_model})"
            else:
                name = f"SoC {soc_model}"

        if not name and platform_code:
            name = f"Qualcomm Snapdragon ({platform_code})"

    # 2. LINUX (Desktop / Wyse Headless)
    if not name and sys.platform.startswith("linux"):
        if os.path.exists("/proc/cpuinfo"):
            try:
                with open("/proc/cpuinfo", "r", encoding="utf-8") as f:
                    for line in f:
                        if "model name" in line:
                            val = line.split(":", 1)[1].strip()
                            if val:
                                name = val
                                break
                        if ("Hardware" in line or "Processor" in line) and not name:
                            val = line.split(":", 1)[1].strip()
                            if val and val.lower() not in ("aarch64", "armv8", "armv7"):
                                name = val
            except Exception:
                pass

    # 3. macOS
    if not name and sys.platform == "darwin":
        try:
            out = subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"], text=True).strip()
            if out:
                name = out
        except Exception:
            pass

    # 4. WINDOWS
    if not name and sys.platform == "win32":
        # Lecture registre Windows (instantanée, zéro WMI)
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
                val, _ = winreg.QueryValueEx(k, "ProcessorNameString")
                if val:
                    name = str(val).strip()
        except Exception:
            pass

        if not name:
            name = platform.processor() or ""

    if not name:
        name = platform.machine() or "CPU Inconnu"

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
    except Exception:
        pass

    for p in glob.glob("/sys/class/thermal/thermal_zone*/temp"):
        try:
            with open(p, "r", encoding="utf-8") as f:
                val = int(f.read().strip())
                c = val / 1000.0 if val > 1000 else float(val)
                if 10.0 <= c <= 125.0:
                    return round(c, 1)
        except Exception:
            pass

    return None


def get_cpu_percent() -> float:
    """
    Calcule la charge CPU globale du système de manière non bloquante et lissée.
    Prise en charge multi-OS : Linux (desktop/headless), Windows, macOS, Android (SELinux).
    """
    global _LAST_CPU_TIMES, _LAST_SMOOTH_CPU_PCT
    now = time.time()
    last_wall, last_total, last_idle = _LAST_CPU_TIMES

    # Si mesuré il y a moins de 1.5s, renvoyer la valeur en cache pour éviter les micro-saccades
    if last_wall > 0 and (now - last_wall) < 1.5:
        return _LAST_SMOOTH_CPU_PCT

    # 1. Linux & Wyse Headless via /proc/stat (non bloquant, instantané)
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
        except Exception:
            pass

    # 2. Repli /proc/loadavg (normalisé par nombre de cœurs) si /proc/stat est restreint par SELinux
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
        except Exception:
            pass

    # 3. Repli psutil sans intervalle bloquant (Windows, macOS)
    try:
        val = psutil.cpu_percent(interval=None)
        if val > 0.0:
            _LAST_SMOOTH_CPU_PCT = round(val, 1)
            _LAST_CPU_TIMES = (now, 0.0, 0.0)
            return _LAST_SMOOTH_CPU_PCT
    except Exception:
        pass

    # 4. Repli /proc/self/stat pour bacs à sable stricts (Android untrusted_app)
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
        except Exception:
            pass

    _LAST_CPU_TIMES = (now, 0.0, 0.0)
    return _LAST_SMOOTH_CPU_PCT
