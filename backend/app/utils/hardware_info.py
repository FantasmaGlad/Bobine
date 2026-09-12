import glob
import logging
import os
import platform
import re
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
    "ram_info": None,
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


def get_ram_info() -> dict[str, Any]:
    """
    Retourne les informations matérielles détaillées de la mémoire vive (RAM) :
    - brand (marque : Hynix, Samsung, Micron, Crucial, Kingston...)
    - type (technologie : DDR2, DDR3, DDR4, DDR5, LPDDR4, LPDDR5, LPDDR5x...)
    - freq (fréquence max : ex. 7500 MHz, 6400 MHz, 3200 MHz...)
    - model_label (libellé commercial formaté pour l'interface utilisateur)
    """
    if _HARDWARE_CACHE.get("ram_info"):
        return _HARDWARE_CACHE["ram_info"]

    brand = ""
    ram_type = ""
    freq = ""

    # 1. Linux via udevadm (lecture SMBIOS sans privilèges root)
    if sys.platform.startswith("linux") and shutil_which("udevadm"):
        try:
            res = subprocess.run(
                ["udevadm", "info", "-p", "/devices/virtual/dmi/id"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    if "MANUFACTURER=" in line and not brand:
                        val = line.split("=", 1)[1].strip()
                        if val and val.lower() not in ("not specified", "not available", "unknown", "n/a", "other", "none"):
                            brand = val
                    if "TYPE=" in line and not ram_type and "TYPE_DETAIL=" not in line:
                        val = line.split("=", 1)[1].strip()
                        if val and val.lower() not in ("unknown", "other", "none", "n/a"):
                            ram_type = val
                    if ("SPEED_MTS=" in line or "CONFIGURED_SPEED_MTS=" in line) and not freq:
                        val = line.split("=", 1)[1].strip()
                        if val.isdigit() and int(val) > 0:
                            freq = f"{val} MHz"
        except Exception:
            pass

    # 2. Linux via dmidecode (si disponible avec ou sans sudo)
    if (not brand or not ram_type or not freq) and shutil_which("dmidecode"):
        for cmd in (["dmidecode", "-t", "17"], ["sudo", "-n", "dmidecode", "-t", "17"]):
            try:
                out = subprocess.check_output(cmd, text=True, timeout=1, stderr=subprocess.DEVNULL)
                for line in out.splitlines():
                    sline = line.strip()
                    if sline.startswith("Manufacturer:") and not brand:
                        val = sline.split(":", 1)[1].strip()
                        if val and val.lower() not in ("not specified", "not available", "unknown", "n/a", "other", "none"):
                            brand = val
                    elif sline.startswith("Type:") and not ram_type and "Type Detail" not in sline:
                        val = sline.split(":", 1)[1].strip()
                        if val and val.lower() not in ("unknown", "other", "none", "n/a"):
                            ram_type = val
                    elif (sline.startswith("Speed:") or sline.startswith("Configured Memory Speed:")) and not freq:
                        val = sline.split(":", 1)[1].strip()
                        if val and not any(k in val.lower() for k in ("unknown", "configured")):
                            freq = val.replace("MT/s", "MHz").strip()
                if brand and ram_type and freq:
                    break
            except Exception:
                pass

    # 3. Linux via inxi si disponible
    if (not brand or not ram_type or not freq) and shutil_which("inxi"):
        try:
            out = subprocess.check_output(["inxi", "-m", "-a", "-c0"], text=True, timeout=2, stderr=subprocess.DEVNULL)
            for line in out.splitlines():
                line_str = line.strip()
                if "manufacturer:" in line_str and not brand:
                    m = re.search(r"manufacturer:\s*([^ ]+)", line_str, re.IGNORECASE)
                    if m and m.group(1).lower() not in ("n/a", "unknown", "none"):
                        brand = m.group(1)
                if "type:" in line_str and not ram_type:
                    m = re.search(r"type:\s*([A-Za-z0-9]+)", line_str, re.IGNORECASE)
                    if m and m.group(1).lower() not in ("n/a", "unknown", "none"):
                        ram_type = m.group(1)
                if "speed:" in line_str and not freq:
                    m = re.search(r"(?:spec|actual):\s*(\d+)\s*(?:MT/s|MHz)", line_str, re.IGNORECASE)
                    if m:
                        freq = f"{m.group(1)} MHz"
        except Exception:
            pass

    # 4. Repli sysfs & logs noyau pour type et fabricant
    if sys.platform.startswith("linux"):
        if not brand:
            for dmi_f in ("/sys/class/dmi/id/sys_vendor", "/sys/class/dmi/id/board_vendor"):
                if os.path.exists(dmi_f):
                    try:
                        with open(dmi_f, "r", encoding="utf-8") as fp:
                            v = fp.read().strip()
                            if v and v.lower() not in ("not specified", "to be filled by o.e.m.", "unknown"):
                                brand = v
                                break
                    except Exception:
                        pass
        if not ram_type:
            try:
                p = subprocess.run(["journalctl", "-b", "0", "--no-pager"], capture_output=True, text=True, timeout=2)
                if p.returncode == 0:
                    m = re.search(r"\b(LP?DDR[2-5][Xx]?)\b", p.stdout, re.IGNORECASE)
                    if m:
                        ram_type = m.group(1).upper()
            except Exception:
                pass

    # 5. Windows via PowerShell / WMI
    elif sys.platform == "win32":
        try:
            ps_cmd = 'Get-CimInstance Win32_PhysicalMemory | Select-Object -First 1 Manufacturer, SMBIOSMemoryType, Speed | ConvertTo-Json'
            out = subprocess.check_output(["powershell", "-NoProfile", "-Command", ps_cmd], text=True, timeout=2)
            import json
            data = json.loads(out)
            if isinstance(data, dict):
                brand = data.get("Manufacturer") or ""
                smbios_type = data.get("SMBIOSMemoryType")
                type_map = {20: "DDR", 21: "DDR2", 24: "DDR3", 26: "DDR4", 30: "DDR5", 34: "LPDDR4", 35: "LPDDR5"}
                if smbios_type in type_map:
                    ram_type = type_map[smbios_type]
                speed = data.get("Speed")
                if speed:
                    freq = f"{speed} MHz"
        except Exception:
            pass

    # 6. macOS via system_profiler
    elif sys.platform == "darwin":
        try:
            out = subprocess.check_output(["system_profiler", "SPMemoryDataType"], text=True, timeout=2)
            for line in out.splitlines():
                sline = line.strip()
                if sline.startswith("Type:") and not ram_type:
                    ram_type = sline.split(":", 1)[1].strip()
                elif sline.startswith("Speed:") and not freq:
                    freq = sline.split(":", 1)[1].strip()
                elif sline.startswith("Manufacturer:") and not brand:
                    brand = sline.split(":", 1)[1].strip()
            if not brand:
                brand = "Apple"
        except Exception:
            pass

    # 7. Android via getprop
    if not ram_type and shutil_which("getprop"):
        for prop in ("ro.boot.dram_type", "ro.boot.ddr_type"):
            try:
                v = subprocess.check_output(["getprop", prop], text=True, timeout=1).strip()
                if v:
                    ram_type = v.upper()
                    break
            except Exception:
                pass

    parts = []
    if brand:
        parts.append(brand)
    if ram_type:
        parts.append(ram_type)
    if freq:
        parts.append(freq)

    model_label = " ".join(parts) if parts else "RAM Système"

    result = {
        "brand": brand or None,
        "type": ram_type or None,
        "freq": freq or None,
        "model_label": model_label,
    }
    _HARDWARE_CACHE["ram_info"] = result
    return result


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
