import glob
import logging
import os
import platform
import subprocess
import sys
import time
from typing import Any

import psutil

logger = logging.getLogger(__name__)

# Heure de démarrage du service backend
_SERVICE_START_TIME = time.time()

# Cache des métadonnées statiques (modèles de CPU, GPU, disque) pour éviter de requêter sysfs à chaque seconde
_HARDWARE_CACHE: dict[str, Any] = {
    "cpu_name": None,
    "gpu_name": None,
    "storage_model": None,
}

# État pour le calcul de puissance par delta RAPL (si power_input n'est pas directement disponible)
_LAST_RAPL_CHECK = 0.0
_LAST_RAPL_ENERGY_UJ = 0


def get_cpu_model_name() -> str:
    """Retourne le nom commercial du processeur (ex: AMD Ryzen 7 8840U, Intel Celeron J4105)."""
    if _HARDWARE_CACHE["cpu_name"]:
        return _HARDWARE_CACHE["cpu_name"]

    name = ""
    try:
        if sys.platform.startswith("linux"):
            if os.path.exists("/proc/cpuinfo"):
                with open("/proc/cpuinfo", "r", encoding="utf-8") as f:
                    for line in f:
                        if "model name" in line:
                            name = line.split(":", 1)[1].strip()
                            break
                        if "Hardware" in line or "Processor" in line:
                            name = line.split(":", 1)[1].strip()
        elif sys.platform == "darwin":
            out = subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"], text=True)
            name = out.strip()
        elif sys.platform == "win32":
            name = platform.processor() or ""
    except Exception as e:
        logger.debug(f"Impossible de déterminer le modèle CPU: {e}")

    if not name:
        name = platform.machine() or "CPU Inconnu"

    _HARDWARE_CACHE["cpu_name"] = name
    return name


def get_gpu_info() -> tuple[str, float | None, float | None]:
    """
    Retourne (gpu_name, gpu_percent, gpu_temp_c).
    Prend en charge AMD (amdgpu), Intel (i915/xe) et NVIDIA (nvidia-smi).
    """
    name = _HARDWARE_CACHE["gpu_name"]
    gpu_percent: float | None = None
    gpu_temp: float | None = None

    # 1. Utilisation GPU (%)
    # AMD GPU via sysfs
    for busy_path in glob.glob("/sys/class/drm/card*/device/gpu_busy_percent"):
        try:
            with open(busy_path, "r", encoding="utf-8") as f:
                val = f.read().strip()
                if val.isdigit():
                    gpu_percent = float(val)
                    break
        except Exception:
            pass

    # NVIDIA via nvidia-smi si disponible
    if gpu_percent is None and shutil_which("nvidia-smi"):
        try:
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=utilization.gpu,temperature.gpu,name", "--format=csv,noheader,nounits"],
                text=True,
                timeout=1,
            )
            line = out.strip().splitlines()[0]
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 2:
                gpu_percent = float(parts[0])
                gpu_temp = float(parts[1])
            if len(parts) >= 3 and not name:
                name = parts[2]
        except Exception:
            pass

    # 2. Température GPU via psutil ou sysfs si pas déjà trouvée
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

    # 3. Nom de modèle GPU si pas encore mis en cache
    if not name:
        # A. Détection dans le nom CPU si GPU intégré (ex: Ryzen w/ Radeon 780M)
        cpu_model = get_cpu_model_name()
        if "w/" in cpu_model:
            parts = cpu_model.split("w/", 1)
            commercial_name = parts[1].strip()
            if not commercial_name.startswith("AMD ") and "Radeon" in commercial_name:
                commercial_name = f"AMD {commercial_name}"
            name = commercial_name

        # B. Détection depuis lspci si pas encore trouvé
        if not name:
            try:
                if shutil_which("lspci"):
                    lspci_out = subprocess.check_output(["lspci"], text=True, timeout=1)
                    for line in lspci_out.splitlines():
                        if any(w in line.lower() for w in ("vga compatible controller", "3d controller", "display controller")):
                            raw = line.split(":", 2)[-1].strip()
                            if "[" in raw and "]" in raw:
                                start = raw.find("[")
                                end = raw.find("]", start)
                                after = raw[end + 1:].strip()
                                name = after.split("(")[0].strip() or raw
                            else:
                                name = raw
                            break
            except Exception:
                pass

        # C. Repli Intel HD/UHD
        if not name:
            if "Intel" in cpu_model:
                name = "Intel HD/UHD Graphics"
            else:
                name = "GPU Inconnu"

        _HARDWARE_CACHE["gpu_name"] = name

    return name, gpu_percent, gpu_temp


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


def get_power_watts() -> float | None:
    """
    Retourne la consommation instantanée en Watts (W) de la machine.
    Lit hwmon power_input, power_supply ou intel-rapl energy_uj.
    """
    global _LAST_RAPL_CHECK, _LAST_RAPL_ENERGY_UJ

    for p in glob.glob("/sys/class/hwmon/*/power*_input"):
        try:
            with open(p, "r", encoding="utf-8") as f:
                val = int(f.read().strip())
                if val > 0:
                    return round(val / 1_000_000.0, 1)
        except Exception:
            pass

    for p in glob.glob("/sys/class/power_supply/*/power_now"):
        try:
            with open(p, "r", encoding="utf-8") as f:
                val = int(f.read().strip())
                if val > 0:
                    return round(val / 1_000_000.0, 1)
        except Exception:
            pass

    for ps_dir in glob.glob("/sys/class/power_supply/*"):
        curr_p = os.path.join(ps_dir, "current_now")
        volt_p = os.path.join(ps_dir, "voltage_now")
        if os.path.exists(curr_p) and os.path.exists(volt_p):
            try:
                with open(curr_p, "r", encoding="utf-8") as f1, open(volt_p, "r", encoding="utf-8") as f2:
                    curr = int(f1.read().strip())
                    volt = int(f2.read().strip())
                    if curr > 0 and volt > 0:
                        watts = (curr * volt) / 1_000_000_000_000.0
                        return round(watts, 1)
            except Exception:
                pass

    for p in glob.glob("/sys/class/powercap/intel-rapl/*/energy_uj"):
        try:
            with open(p, "r", encoding="utf-8") as f:
                current_energy = int(f.read().strip())
            now = time.time()
            if _LAST_RAPL_CHECK > 0 and now > _LAST_RAPL_CHECK:
                delta_sec = now - _LAST_RAPL_CHECK
                delta_energy = current_energy - _LAST_RAPL_ENERGY_UJ
                if delta_sec > 0 and delta_energy > 0:
                    watts = (delta_energy / 1_000_000.0) / delta_sec
                    _LAST_RAPL_CHECK = now
                    _LAST_RAPL_ENERGY_UJ = current_energy
                    if 0.5 <= watts <= 300.0:
                        return round(watts, 1)
            _LAST_RAPL_CHECK = now
            _LAST_RAPL_ENERGY_UJ = current_energy
            break
        except Exception:
            pass

    return None


def get_storage_model() -> str:
    """Retourne le modèle matériel du disque de stockage principal (SSD, NVMe, eMMC)."""
    if _HARDWARE_CACHE["storage_model"]:
        return _HARDWARE_CACHE["storage_model"]

    model = ""
    for p in glob.glob("/sys/block/*/device/model"):
        if any(x in p for x in ("loop", "ram", "zram")):
            continue
        try:
            with open(p, "r", encoding="utf-8") as f:
                val = f.read().strip()
                if val:
                    model = val
                    break
        except Exception:
            pass

    if not model and shutil_which("lsblk"):
        try:
            out = subprocess.check_output(
                ["lsblk", "-d", "-n", "-o", "MODEL"],
                text=True,
                timeout=1,
            )
            for line in out.splitlines():
                line = line.strip()
                if line:
                    model = line
                    break
        except Exception:
            pass

    if not model:
        model = "Stockage Système"

    _HARDWARE_CACHE["storage_model"] = model
    return model


def get_runtime_info() -> dict[str, Any]:
    """Retourne les informations d'uptime du système et de runtime de Bobine."""
    now = time.time()
    service_uptime = int(now - _SERVICE_START_TIME)

    system_uptime = 0
    try:
        system_uptime = int(now - psutil.boot_time())
    except Exception:
        if os.path.exists("/proc/uptime"):
            try:
                with open("/proc/uptime", "r", encoding="utf-8") as f:
                    system_uptime = int(float(f.read().split()[0]))
            except Exception:
                system_uptime = service_uptime

    return {
        "service_uptime_seconds": service_uptime,
        "service_uptime_formatted": format_duration_short(service_uptime),
        "system_uptime_seconds": system_uptime,
        "system_uptime_formatted": format_duration_short(system_uptime),
    }


def format_duration_short(seconds: int) -> str:
    """Formate une durée en 'Xj Yh Zm' ou 'Yh Zm'."""
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    if days > 0:
        return f"{days}j {hours}h {minutes}m"
    if hours > 0:
        return f"{hours}h {minutes:02d}m"
    return f"{minutes}m"


def shutil_which(cmd: str) -> bool:
    """Vérifie si une commande existe dans PATH sans lever d'exception."""
    import shutil
    return shutil.which(cmd) is not None
