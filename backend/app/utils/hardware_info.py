import glob
import logging
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from typing import Any

import psutil

logger = logging.getLogger(__name__)

# Heure de démarrage du service backend
_SERVICE_START_TIME = time.time()

# Cache des métadonnées statiques (modèles de CPU, GPU, disque, RAM) pour éviter de requêter sysfs/wmi/udevadm à chaque seconde
_HARDWARE_CACHE: dict[str, Any] = {
    "cpu_name": None,
    "gpu_name": None,
    "storage_model": None,
    "ram_info": None,
}

# État pour le calcul de puissance par delta RAPL (si power_input n'est pas directement disponible)
_LAST_RAPL_CHECK = 0.0
_LAST_RAPL_ENERGY_UJ = 0


def shutil_which(cmd: str) -> bool:
    """Vérifie si une commande existe dans PATH sans lever d'exception."""
    return shutil.which(cmd) is not None


def _get_android_prop(prop_name: str) -> str:
    """Lit une propriété Android via getprop ou /system/build.prop."""
    if shutil_which("getprop"):
        try:
            out = subprocess.check_output(["getprop", prop_name], text=True, timeout=1).strip()
            if out:
                return out
        except Exception:
            pass

    for build_prop in ("/system/build.prop", "/default.prop", "/vendor/build.prop"):
        if os.path.exists(build_prop):
            try:
                with open(build_prop, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if line.startswith(f"{prop_name}="):
                            return line.split("=", 1)[1].strip()
            except Exception:
                pass
    return ""


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
    is_android = hasattr(sys, "getandroidapilevel") or shutil_which("getprop")

    # 1. ANDROID : détection SoC via getprop et sysfs
    if is_android:
        soc_model = _get_android_prop("ro.soc.model").strip()
        platform_code = _get_android_prop("ro.board.platform").strip()
        manufacturer = _get_android_prop("ro.soc.manufacturer").strip()

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


def get_gpu_info() -> tuple[str, float | None, float | None]:
    """
    Retourne (gpu_name, gpu_percent, gpu_temp_c).
    Prend en charge AMD (amdgpu), Intel (i915/xe), NVIDIA (nvidia-smi),
    Apple Silicon (macOS) et Qualcomm Adreno / Mali (Android).
    """
    name = _HARDWARE_CACHE["gpu_name"]
    gpu_percent: float | None = None
    gpu_temp: float | None = None
    is_android = hasattr(sys, "getandroidapilevel") or shutil_which("getprop")

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

    # 4. macOS : lecture batterie via ioreg
    if sys.platform == "darwin":
        try:
            out = subprocess.check_output(["ioreg", "-rc", "AppleSmartBattery"], text=True, timeout=1)
            volt = None
            amp = None
            for line in out.splitlines():
                if '"Voltage" =' in line:
                    volt = int(line.split("=", 1)[1].strip())
                elif '"Amperage" =' in line:
                    amp = abs(int(line.split("=", 1)[1].strip()))
            if volt and amp and volt > 0 and amp > 0:
                watts = (volt * amp) / 1_000_000.0
                if 0.5 <= watts <= 300.0:
                    return round(watts, 1)
        except Exception:
            pass

    return None


def get_storage_model() -> str:
    """
    Retourne le modèle matériel du disque de stockage principal (SSD, NVMe, UFS, eMMC).
    Prise en charge multi-OS : Linux, macOS, Windows, Android.
    """
    if _HARDWARE_CACHE["storage_model"]:
        return _HARDWARE_CACHE["storage_model"]

    model = ""
    is_android = hasattr(sys, "getandroidapilevel") or shutil_which("getprop")

    # 1. ANDROID : détection bus UFS / eMMC
    if is_android:
        bootdevice = _get_android_prop("ro.boot.bootdevice") or _get_android_prop("ro.boot.boot_devices")
        soc_model = _get_android_prop("ro.soc.model").upper()

        if "ufshc" in bootdevice.lower():
            # UFS 4.0 sur les puces haut de gamme Snapdragon 8 Elite (SM8750/SM8735P) et 8 Gen 3
            if any(s in soc_model for s in ("SM8750", "SM8735", "SUN", "SM8650", "PINEAPPLE")):
                model = "Stockage Flash UFS 4.0 (256 Go)"
            elif any(s in soc_model for s in ("SM8550", "KALAMA", "SM8475")):
                model = "Stockage Flash UFS 3.1"
            else:
                model = "Stockage Flash UFS"
        elif "mmc" in bootdevice.lower():
            model = "Stockage Flash eMMC 5.1"

    # 2. LINUX (Desktop & Wyse Headless)
    if not model and sys.platform.startswith("linux"):
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
                out = subprocess.check_output(["lsblk", "-d", "-n", "-o", "MODEL"], text=True, timeout=1)
                for line in out.splitlines():
                    line = line.strip()
                    if line:
                        model = line
                        break
            except Exception:
                pass

    # 3. macOS
    if not model and sys.platform == "darwin":
        try:
            out = subprocess.check_output(["diskutil", "info", "/"], text=True, timeout=2)
            for line in out.splitlines():
                if "Device / Media Name:" in line:
                    model = line.split(":", 1)[1].strip()
                    break
        except Exception:
            pass

    # 4. WINDOWS
    if not model and sys.platform == "win32":
        try:
            out = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_DiskDrive).Model"],
                text=True,
                timeout=2,
            )
            for line in out.splitlines():
                sline = line.strip()
                if sline:
                    model = sline
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
    - type (technologie : DDR4, DDR5, LPDDR4, LPDDR5, LPDDR5x...)
    - freq (fréquence max : ex. 8533 MT/s, 6400 MHz, 3200 MHz...)
    - model_label (libellé commercial formaté pour l'interface utilisateur)
    """
    if _HARDWARE_CACHE.get("ram_info"):
        return _HARDWARE_CACHE["ram_info"]

    brand = ""
    ram_type = ""
    freq = ""
    is_android = hasattr(sys, "getandroidapilevel") or shutil_which("getprop")

    # 1. ANDROID : détection de la RAM via spécification SoC et getprop
    if is_android:
        soc_model = _get_android_prop("ro.soc.model").upper()
        dram_prop = _get_android_prop("ro.boot.dram_type") or _get_android_prop("ro.boot.ddr_type")
        if dram_prop:
            ram_type = dram_prop.upper()

        if any(s in soc_model for s in ("SM8750", "SM8735", "SUN")):
            ram_type = "LPDDR5X"
            freq = "8533 MT/s"
        elif any(s in soc_model for s in ("SM8650", "PINEAPPLE", "SM8635")):
            ram_type = "LPDDR5X"
            freq = "8533 MT/s"
        elif any(s in soc_model for s in ("SM8550", "KALAMA")):
            ram_type = "LPDDR5X"
            freq = "8533 MT/s"
        elif any(s in soc_model for s in ("SM8475", "SM8450", "TARO", "CAPE")):
            ram_type = "LPDDR5"
            freq = "6400 MT/s"

    # 2. LINUX (Desktop / Wyse Headless) via udevadm SMBIOS
    if not brand and sys.platform.startswith("linux") and shutil_which("udevadm"):
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

    # 3. LINUX via dmidecode
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

    # 4. WINDOWS via PowerShell / WMI Win32_PhysicalMemory
    if sys.platform == "win32" and (not brand or not ram_type or not freq):
        try:
            out = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_PhysicalMemory | Select-Object -Property Manufacturer,SMBIOSMemoryType,Speed | ConvertTo-Json"],
                text=True,
                timeout=2,
            )
            import json
            data = json.loads(out)
            item = data[0] if isinstance(data, list) and data else data
            if isinstance(item, dict):
                if not brand and item.get("Manufacturer"):
                    b = str(item["Manufacturer"]).strip()
                    if b.lower() not in ("unknown", "not specified"):
                        brand = b
                if not freq and item.get("Speed"):
                    freq = f"{item['Speed']} MHz"
                if not ram_type and item.get("SMBIOSMemoryType"):
                    code = item["SMBIOSMemoryType"]
                    smbios_map = {24: "DDR3", 26: "DDR4", 30: "LPDDR4", 34: "DDR5", 35: "LPDDR5"}
                    if code in smbios_map:
                        ram_type = smbios_map[code]
        except Exception:
            pass

    # 5. macOS via system_profiler
    if sys.platform == "darwin" and (not brand or not ram_type or not freq):
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
