"""Carte graphique : nom, charge, température."""

import glob
import os
import re
import subprocess
import sys

import psutil

from .cpu import get_cpu_model_name
from .probe import _HARDWARE_CACHE, _get_android_prop, is_android_system, shutil_which


def get_gpu_info() -> tuple[str, float | None, float | None]:
    """
    Retourne (gpu_name, gpu_percent, gpu_temp_c).
    Prend en charge AMD (amdgpu), Intel (i915/xe), NVIDIA (nvidia-smi),
    Apple Silicon (macOS) et Qualcomm Adreno / Mali (Android).
    """
    name = _HARDWARE_CACHE["gpu_name"]
    gpu_percent: float | None = None
    gpu_temp: float | None = None
    is_android = is_android_system()

    # 1. ANDROID (Qualcomm Adreno / ARM Mali)
    if is_android:
        # A. Nom GPU via /sys/class/kgsl/kgsl-3d0/gpu_model
        if not name and os.path.exists("/sys/class/kgsl/kgsl-3d0/gpu_model"):
            try:
                with open("/sys/class/kgsl/kgsl-3d0/gpu_model", "r", encoding="utf-8") as f:
                    raw_gpu = f.read().strip()
                    if raw_gpu:
                        # Ex: 'Adreno825' -> 'Qualcomm Adreno 825'
                        m = re.match(r"([A-Za-z]+)(\d+)", raw_gpu)
                        if m:
                            name = f"Qualcomm {m.group(1)} {m.group(2)}"
                        else:
                            name = f"Qualcomm {raw_gpu}"
            except Exception:
                pass

        # B. Dumpsys SurfaceFlinger pour GLES renderer
        if not name and shutil_which("dumpsys"):
            try:
                out = subprocess.check_output(["dumpsys", "SurfaceFlinger"], text=True, timeout=1)
                for line in out.splitlines():
                    if "GLES:" in line:
                        parts = line.split("GLES:", 1)[1].split(",")
                        if len(parts) >= 2:
                            vendor = parts[0].strip()
                            renderer = parts[1].strip().replace("(TM)", "").strip()
                            name = f"{vendor} {renderer}"
                            break
            except Exception:
                pass

        if not name:
            egl = _get_android_prop("ro.hardware.egl").strip()
            if egl:
                name = f"Qualcomm {egl.capitalize()}"

        # C. Température GPU Android via /sys/class/thermal
        if gpu_temp is None:
            for tz in glob.glob("/sys/class/thermal/thermal_zone*"):
                type_file = os.path.join(tz, "type")
                temp_file = os.path.join(tz, "temp")
                if os.path.exists(type_file) and os.path.exists(temp_file):
                    try:
                        with open(type_file, "r", encoding="utf-8") as ft:
                            t_type = ft.read().strip().lower()
                        if any(k in t_type for k in ("gpu-0", "gpu-1", "gpu0", "gpuss", "gpu")):
                            with open(temp_file, "r", encoding="utf-8") as ftemp:
                                t_val = int(ftemp.read().strip())
                                c = t_val / 1000.0 if t_val > 1000 else float(t_val)
                                if 15.0 <= c <= 115.0:
                                    gpu_temp = round(c, 1)
                                    break
                    except Exception:
                        pass

        # D. Charge GPU Android via /sys/class/kgsl/kgsl-3d0/gpubusy
        if gpu_percent is None and os.path.exists("/sys/class/kgsl/kgsl-3d0/gpubusy"):
            try:
                with open("/sys/class/kgsl/kgsl-3d0/gpubusy", "r", encoding="utf-8") as f:
                    vals = f.read().split()
                    if len(vals) >= 2:
                        busy, total = int(vals[0]), int(vals[1])
                        if total > 0:
                            gpu_percent = round((busy / total) * 100.0, 1)
            except Exception:
                pass

    # 2. LINUX DESKTOP & HEADLESS : AMD GPU via sysfs
    if gpu_percent is None:
        for busy_path in glob.glob("/sys/class/drm/card*/device/gpu_busy_percent"):
            try:
                with open(busy_path, "r", encoding="utf-8") as f:
                    val = f.read().strip()
                    if val.isdigit():
                        gpu_percent = float(val)
                        break
            except Exception:
                pass

    # 3. NVIDIA via nvidia-smi (Linux & Windows)
    if (gpu_percent is None or not name) and shutil_which("nvidia-smi"):
        try:
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=utilization.gpu,temperature.gpu,name", "--format=csv,noheader,nounits"],
                text=True,
                timeout=1,
            )
            line = out.strip().splitlines()[0]
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 2 and gpu_percent is None:
                gpu_percent = float(parts[0])
            if len(parts) >= 2 and gpu_temp is None:
                gpu_temp = float(parts[1])
            if len(parts) >= 3 and not name:
                name = parts[2]
        except Exception:
            pass

    # 4. Température GPU via psutil si pas déjà trouvée
    if gpu_temp is None:
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                for k in ("amdgpu", "nouveau", "nvidia"):
                    if k in temps and temps[k]:
                        gpu_temp = round(temps[k][0].current, 1)
                        break
        except Exception:
            pass

    # 5. macOS : GPU Apple Silicon
    if not name and sys.platform == "darwin":
        try:
            out = subprocess.check_output(["system_profiler", "SPDisplaysDataType"], text=True, timeout=2)
            for line in out.splitlines():
                sline = line.strip()
                if sline.startswith("Chipset Model:"):
                    name = sline.split(":", 1)[1].strip()
                    break
        except Exception:
            pass

    # 6. Windows : WMI Win32_VideoController
    if not name and sys.platform == "win32":
        try:
            out = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_VideoController).Name"],
                text=True,
                timeout=2,
            )
            lines = [line.strip() for line in out.splitlines() if line.strip()]
            # Filtrer les pilotes virtuels (Miracast, RDP...)
            valid_gpus = [g for g in lines if not any(x in g.lower() for x in ("virtual", "remote", "rdp", "basic display"))]
            if valid_gpus:
                name = valid_gpus[0]
        except Exception:
            pass

    # 7. Linux lspci & détection dans CPU
    if not name:
        cpu_model = get_cpu_model_name()
        if "w/" in cpu_model:
            parts = cpu_model.split("w/", 1)
            commercial_name = parts[1].strip()
            if not commercial_name.startswith("AMD ") and "Radeon" in commercial_name:
                commercial_name = f"AMD {commercial_name}"
            name = commercial_name

        if not name and shutil_which("lspci"):
            try:
                lspci_out = subprocess.check_output(["lspci"], text=True, timeout=1)
                for line in lspci_out.splitlines():
                    if any(w in line.lower() for w in ("vga compatible controller", "3d controller", "display controller")):
                        raw = line.split(":", 2)[-1].strip()
                        if "[" in raw and "]" in raw:
                            start = raw.find("[")
                            end = raw.find("]", start)
                            bracket_content = raw[start + 1:end].strip()
                            if bracket_content:
                                if "Intel" in raw and not bracket_content.lower().startswith("intel"):
                                    name = f"Intel {bracket_content}"
                                else:
                                    name = bracket_content
                            else:
                                name = raw.split("(")[0].strip()
                        else:
                            name = raw.split("(")[0].strip()
                        break
            except Exception:
                pass

        if not name:
            if "Intel" in cpu_model:
                name = "Intel HD/UHD Graphics"
            else:
                name = "GPU Inconnu"

    _HARDWARE_CACHE["gpu_name"] = name
    return name, gpu_percent, gpu_temp
