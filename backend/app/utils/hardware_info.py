from datetime import datetime, timedelta, timezone
import glob
import logging
import os
from pathlib import Path
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

# État de lissage CPU non bloquant
_LAST_CPU_TIMES: tuple[float, float, float] = (0.0, 0.0, 0.0)  # (wall_time, total_ticks, idle_ticks)
_LAST_SMOOTH_CPU_PCT: float = 0.0

# Suivi de l'énergie consommée depuis le début du runtime (Wh)
_CUMULATIVE_ENERGY_WH: float = 0.0
_LAST_ENERGY_SAMPLE_TIME: float = 0.0



def shutil_which(cmd: str) -> bool:
    """Vérifie si une commande existe dans PATH sans lever d'exception."""
    try:
        return shutil.which(cmd) is not None
    except Exception:
        return False


def is_android_system() -> bool:
    """Détecte si l'environnement d'exécution est Android (Chaquopy ou shell Android Linux)."""
    return hasattr(sys, "getandroidapilevel") or (sys.platform.startswith("linux") and shutil_which("getprop"))


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
    is_android = is_android_system()

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
    Prise en charge multi-OS : Linux (APU/GPU hwmon, RAPL, batterie/secteur),
    Android (BatteryManager sur batterie et sur chargeur), macOS (ioreg/AppleSmartBattery),
    et repli physique proportionnel à la charge CPU.
    """
    global _LAST_RAPL_CHECK, _LAST_RAPL_ENERGY_UJ

    # 1. ANDROID (Chaquopy) : gestion batterie et chargeur secteur
    if is_android_system():
        try:
            from com.chaquo.python import Python
            from android.content import Context, Intent, IntentFilter
            from android.os import BatteryManager
            app_ctx = Python.getPlatform().getApplication()
            bm = app_ctx.getSystemService(Context.BATTERY_SERVICE)
            filt = IntentFilter(Intent.ACTION_BATTERY_CHANGED)
            intent = app_ctx.registerReceiver(None, filt)
            if intent:
                plugged = intent.getIntExtra(BatteryManager.EXTRA_PLUGGED, 0)
                status = intent.getIntExtra(BatteryManager.EXTRA_STATUS, -1)
                voltage_mv = intent.getIntExtra(BatteryManager.EXTRA_VOLTAGE, -1)
                current_ua = bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CURRENT_NOW)
                if current_ua == -2147483648:  # Integer.MIN_VALUE si non disponible
                    current_ua = 0

                cpu_pct = get_cpu_percent()

                # A. Branché au secteur (plugged > 0 ou statut CHARGING / FULL)
                if plugged > 0 or status in (BatteryManager.BATTERY_STATUS_CHARGING, BatteryManager.BATTERY_STATUS_FULL):
                    # Consommation de fonctionnement actif de la tablette (écran 3K 144Hz + SoC + radios)
                    active_w = 3.2 + (cpu_pct / 100.0) * 5.0

                    if status == BatteryManager.BATTERY_STATUS_CHARGING and current_ua != 0 and abs(current_ua) < 20_000_000:
                        v = (voltage_mv / 1000.0) if voltage_mv > 0 else 4.2
                        charge_w = (abs(current_ua) / 1_000_000.0) * v
                        total_w = charge_w + active_w
                        return round(min(120.0, max(1.0, total_w)), 1)
                    else:
                        # Batterie pleine (100%) ou maintien : la tablette fonctionne sur l'alimentation externe
                        return round(min(60.0, max(1.5, active_w)), 1)

                # B. Sur batterie (débranché)
                if current_ua != 0 and abs(current_ua) < 20_000_000 and voltage_mv > 0:
                    watts = (abs(current_ua) / 1_000_000.0) * (voltage_mv / 1000.0)
                    if 0.5 <= watts <= 60.0:
                        return round(watts, 1)

                # Repli sur batterie si le capteur de courant est masqué par le fabricant
                return round(2.8 + (cpu_pct / 100.0) * 4.5, 1)
        except Exception:
            pass

    # 2. LINUX (Desktop, Laptop, Wyse Headless) : Capteurs matériels SoC / APU / GPU / RAPL / Batterie
    if sys.platform.startswith("linux") and not is_android_system():
        # A. Capteurs matériels SoC / APU / GPU / CPU (prioritaires sur la batterie)
        for h_dir in glob.glob("/sys/class/hwmon/hwmon*"):
            name_file = os.path.join(h_dir, "name")
            name = ""
            if os.path.exists(name_file):
                try:
                    with open(name_file, "r", encoding="utf-8") as f:
                        name = f.read().strip().lower()
                except Exception:
                    pass
            # On ignore les sondes batterie ici (traitées ci-dessous selon leur statut AC/DC)
            if "bat" in name or "battery" in name:
                continue

            for p in glob.glob(os.path.join(h_dir, "power*_input")) + glob.glob(os.path.join(h_dir, "power*_average")):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        val = int(f.read().strip())
                        if 500_000 <= val <= 500_000_000:
                            return round(val / 1_000_000.0, 1)
                except Exception:
                    pass

        # B. Intel / AMD RAPL (Running Average Power Limit) — Idéal Wyse 5070 et serveurs headless
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

        # C. Gestion intelligente batterie / alimentation secteur (Laptops Linux)
        is_on_ac = False
        for ac_dir in glob.glob("/sys/class/power_supply/*"):
            type_file = os.path.join(ac_dir, "type")
            online_file = os.path.join(ac_dir, "online")
            if os.path.exists(type_file) and os.path.exists(online_file):
                try:
                    t = open(type_file, "r").read().strip().lower()
                    o = open(online_file, "r").read().strip()
                    if t in ("mains", "ac", "usb") and o == "1":
                        is_on_ac = True
                        break
                except Exception:
                    pass

        for bat_dir in glob.glob("/sys/class/power_supply/*"):
            type_file = os.path.join(bat_dir, "type")
            if os.path.exists(type_file):
                try:
                    if open(type_file, "r").read().strip().lower() != "battery":
                        continue
                except Exception:
                    pass

            status_file = os.path.join(bat_dir, "status")
            status = ""
            if os.path.exists(status_file):
                try:
                    status = open(status_file, "r").read().strip().lower()
                except Exception:
                    pass

            power_file = os.path.join(bat_dir, "power_now")
            curr_file = os.path.join(bat_dir, "current_now")
            volt_file = os.path.join(bat_dir, "voltage_now")
            bat_watts = None

            if os.path.exists(power_file):
                try:
                    val = int(open(power_file, "r").read().strip())
                    if val > 0:
                        bat_watts = val / 1_000_000.0
                except Exception:
                    pass
            elif os.path.exists(curr_file) and os.path.exists(volt_file):
                try:
                    c = int(open(curr_file, "r").read().strip())
                    v = int(open(volt_file, "r").read().strip())
                    if c > 0 and v > 0:
                        bat_watts = (c * v) / 1_000_000_000_000.0
                except Exception:
                    pass

            # Sur batterie : décharge réelle du PC portable
            if status == "discharging" and bat_watts and bat_watts >= 0.5:
                return round(bat_watts, 1)

            # Branché au secteur (charge ou plein)
            if status in ("charging", "full", "not charging") or is_on_ac:
                cpu_pct = get_cpu_percent()
                base_laptop_w = 9.0 + (cpu_pct / 100.0) * 22.0
                if status == "charging" and bat_watts and bat_watts > 1.0:
                    return round(bat_watts + base_laptop_w, 1)
                else:
                    return round(base_laptop_w, 1)

    # 5. macOS : AppleSmartBattery (batterie et chargeur)
    if sys.platform == "darwin":
        try:
            out = subprocess.check_output(["ioreg", "-rc", "AppleSmartBattery"], text=True, timeout=1)
            volt = None
            amp = None
            is_charging = False
            external_connected = False
            for line in out.splitlines():
                if '"Voltage" =' in line:
                    volt = int(line.split("=", 1)[1].strip())
                elif '"Amperage" =' in line:
                    amp = int(line.split("=", 1)[1].strip())
                elif '"IsCharging" =' in line:
                    is_charging = "Yes" in line or "true" in line.lower()
                elif '"ExternalConnected" =' in line:
                    external_connected = "Yes" in line or "true" in line.lower()

            cpu_pct = get_cpu_percent()
            base_mac_w = 4.5 + (cpu_pct / 100.0) * 22.0

            if external_connected:
                if is_charging and amp and amp > 0 and volt and volt > 0:
                    charge_w = (volt * amp) / 1_000_000.0
                    return round(charge_w + base_mac_w, 1)
                else:
                    return round(base_mac_w, 1)
            elif volt and amp and volt > 0 and amp != 0:
                watts = (volt * abs(amp)) / 1_000_000.0
                if 0.5 <= watts <= 150.0:
                    return round(watts, 1)
        except Exception:
            pass

    # 6. Repli physique universel multi-OS et multi-facteur (Desktop fixe, Mini-PC, Mac mini, Laptops branchés ou sur batterie)
    try:
        cpu_pct = get_cpu_percent()
        nb_cores = os.cpu_count() or 4

        bat = None
        try:
            bat = psutil.sensors_battery()
        except Exception:
            pass

        # Cas A : Appareil portable avec batterie (Laptop Windows, MacBook sans ioreg, Laptop Linux)
        if bat is not None:
            if not bat.power_plugged:
                # Sur batterie (décharge active)
                base_discharge = 6.0 + (cpu_pct / 100.0) * (nb_cores * 1.8)
                return round(min(65.0, max(3.0, base_discharge)), 1)
            else:
                # Sur secteur AC / branché
                base_laptop_ac = 9.0 + (cpu_pct / 100.0) * 22.0
                if hasattr(bat, "percent") and bat.percent is not None and bat.percent < 90:
                    # En cours de charge active de la batterie
                    charge_power = 25.0
                    return round(min(120.0, max(12.0, base_laptop_ac + charge_power)), 1)
                else:
                    # Batterie pleine (100%) ou en maintien de charge
                    return round(min(65.0, max(7.0, base_laptop_ac)), 1)

        # Cas B : Appareil fixe sans batterie (PC fixe tour Windows, Mac mini / Mac Studio, Wyse headless / mini-PC)
        if sys.platform == "win32":
            # PC Fixe Windows (tour de bureau : alimentation ATX, CPU desktop, GPU dédié ou chipset)
            base_desktop = 28.0 + min(25.0, max(0.0, (nb_cores - 4) * 2.5))
            active_desktop = base_desktop + (cpu_pct / 100.0) * (nb_cores * 4.5)
            return round(min(450.0, max(20.0, active_desktop)), 1)
        elif sys.platform == "darwin":
            # Mac mini / Mac Studio (Apple Silicon ultra-efficient sans batterie)
            base_macmini = 6.5 + min(8.0, max(0.0, (nb_cores - 4) * 1.0))
            active_macmini = base_macmini + (cpu_pct / 100.0) * (nb_cores * 3.0)
            return round(min(120.0, max(5.0, active_macmini)), 1)
        else:
            # Linux Headless / Appliance Dell Wyse 5070 / mini-PC Celeron
            base_mini = min(12.0, max(4.0, nb_cores * 1.2))
            active_mini = base_mini + (cpu_pct / 100.0) * (nb_cores * 2.5)
            return round(min(90.0, max(3.5, active_mini)), 1)
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
    is_android = is_android_system()

    # 1. ANDROID : détection bus UFS / eMMC
    if is_android:
        bootdevice = _get_android_prop("ro.boot.bootdevice") or _get_android_prop("ro.boot.boot_devices")
        soc_model = _get_android_prop("ro.soc.model").upper()

        if "ufshc" in bootdevice.lower():
            # UFS 4.0 sur les puces haut de gamme Snapdragon 8 Elite (SM8750/SM8735P) et 8 Gen 3
            if any(s in soc_model for s in ("SM8750", "SM8735", "SUN", "SM8650", "PINEAPPLE")):
                model = "Flash UFS 4.0 (256 Go)"
            elif any(s in soc_model for s in ("SM8550", "KALAMA", "SM8475")):
                model = "Flash UFS 3.1"
            else:
                model = "Flash UFS"
        elif "mmc" in bootdevice.lower():
            model = "Flash eMMC 5.1"

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
    is_android = is_android_system()

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


def get_storage_usage() -> dict[str, Any]:
    """
    Mesure l'espace disque réel sur le dossier média applicatif (et non sur / qui
    est un ramdisk système de 700 Mo en lecture seule sous Android).
    """
    try:
        from app.config import runtime_settings
        media_dir = Path(runtime_settings.media_dir)
    except Exception:
        media_dir = Path("data")

    probe = media_dir
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    if not probe.exists():
        probe = Path(".")

    try:
        usage = shutil.disk_usage(probe)
        used_pct = round((usage.used / usage.total) * 100, 1) if usage.total else 0.0
        return {
            "total_bytes": usage.total,
            "used_bytes": usage.used,
            "free_bytes": usage.free,
            "used_percent": used_pct,
        }
    except Exception:
        return {"total_bytes": 0, "used_bytes": 0, "free_bytes": 0, "used_percent": 0.0}


def update_cumulative_energy(watts: float | None) -> None:
    """Met à jour l'énergie cumulée en Watt-heures (Wh)."""
    global _CUMULATIVE_ENERGY_WH, _LAST_ENERGY_SAMPLE_TIME
    now = time.time()
    if _LAST_ENERGY_SAMPLE_TIME > 0 and watts and watts > 0:
        delta_hours = (now - _LAST_ENERGY_SAMPLE_TIME) / 3600.0
        if 0 < delta_hours < 0.1:  # Ignorer les sauts temporels > 6 min
            _CUMULATIVE_ENERGY_WH += watts * delta_hours
    _LAST_ENERGY_SAMPLE_TIME = now


def get_cumulative_energy_wh() -> float:
    return round(_CUMULATIVE_ENERGY_WH, 2)


def get_average_power_watts() -> float | None:
    now = time.time()
    runtime_hours = (now - _SERVICE_START_TIME) / 3600.0
    if runtime_hours > 0 and _CUMULATIVE_ENERGY_WH > 0:
        return round(_CUMULATIVE_ENERGY_WH / runtime_hours, 1)
    return None


def get_runtime_info() -> dict[str, Any]:
    """Retourne les informations d'uptime du système et de runtime de Bobine."""
    now = time.time()
    service_uptime = int(now - _SERVICE_START_TIME)

    system_uptime = 0
    is_android = is_android_system()

    # 1. ANDROID : Uptime système exact via SystemClock (non affecté par SELinux /proc/uptime)
    if is_android:
        try:
            from android.os import SystemClock
            system_uptime = int(SystemClock.elapsedRealtime() / 1000)
        except Exception:
            pass

    # 2. Linux & Wyse Headless via /proc/uptime
    if system_uptime <= 0 and os.path.exists("/proc/uptime"):
        try:
            with open("/proc/uptime", "r", encoding="utf-8") as f:
                system_uptime = int(float(f.read().split()[0]))
        except Exception:
            pass

    # 3. Windows & macOS via psutil boot_time
    if system_uptime <= 0:
        try:
            system_uptime = int(now - psutil.boot_time())
        except Exception:
            system_uptime = service_uptime

    avg_w = get_average_power_watts()
    wh = get_cumulative_energy_wh()

    return {
        "service_uptime_seconds": service_uptime,
        "service_uptime_formatted": format_duration_short(service_uptime),
        "app_runtime_formatted": format_duration_short(service_uptime),
        "system_uptime_seconds": system_uptime,
        "system_uptime_formatted": format_duration_short(system_uptime),
        "uptime_formatted": format_duration_short(system_uptime),
        "cumulative_energy_wh": wh if wh > 0 else None,
        "average_power_watts": avg_w,
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


def get_system_telemetry_payload() -> dict[str, Any]:
    """
    Génère la télémétrie matérielle complète unifiée consommée par
    /api/settings/system et /api/metrics/dashboard.
    """
    gpu_name, gpu_percent, gpu_temp_c = get_gpu_info()
    ram_info = get_ram_info()
    storage_info = get_storage_usage()
    power_watts = get_power_watts()
    update_cumulative_energy(power_watts)
    cpu_pct = get_cpu_percent()
    cpu_temp = get_cpu_temp()
    runtime = get_runtime_info()

    # Mémoire RAM
    mem_total, mem_used, mem_percent = 0, 0, 0.0
    try:
        vm = psutil.virtual_memory()
        mem_total = vm.total
        mem_used = vm.total - vm.available
        mem_percent = vm.percent
    except Exception:
        try:
            with open("/proc/meminfo", "r", encoding="utf-8") as f:
                lines = f.readlines()
            m = {}
            for l in lines:
                if ":" in l:
                    k, v = l.split(":", 1)
                    m[k.strip()] = int(v.strip().split()[0]) * 1024
            mem_total = m.get("MemTotal", 0)
            avail = m.get("MemAvailable", m.get("MemFree", 0))
            mem_used = max(0, mem_total - avail)
            mem_percent = round((mem_used / mem_total) * 100, 1) if mem_total else 0.0
        except Exception:
            pass

    return {
        "cpu_name": get_cpu_model_name(),
        "cpu_percent": cpu_pct,
        "cpu_temp_c": cpu_temp,
        "gpu_name": gpu_name,
        "gpu_percent": gpu_percent,
        "gpu_temp_c": gpu_temp_c,
        "power_watts": power_watts,
        "storage_model": get_storage_model(),
        "storage_used_percent": storage_info["used_percent"],
        "storage_free_bytes": storage_info["free_bytes"],
        "storage_total_bytes": storage_info["total_bytes"],
        "storage": storage_info,
        "memory_total_bytes": mem_total,
        "memory_used_bytes": mem_used,
        "memory_percent": mem_percent,
        "ram_brand": ram_info.get("brand"),
        "ram_type": ram_info.get("type"),
        "ram_freq": ram_info.get("freq"),
        "ram_model": ram_info.get("model_label"),
        "runtime": runtime,
    }


def record_hardware_snapshot(db, extra: dict[str, Any] | None = None) -> None:
    """Enregistre un instantané matériel dans la table system_metrics_history."""
    try:
        telemetry = get_system_telemetry_payload()
        from app.models import SystemMetricsHistory
        import json
        extra_json = json.dumps(extra) if extra else None
        snapshot = SystemMetricsHistory(
            cpu_percent=telemetry.get("cpu_percent"),
            cpu_temp_c=telemetry.get("cpu_temp_c"),
            gpu_percent=telemetry.get("gpu_percent"),
            gpu_temp_c=telemetry.get("gpu_temp_c"),
            memory_percent=telemetry.get("memory_percent"),
            memory_used_bytes=telemetry.get("memory_used_bytes"),
            storage_used_percent=telemetry.get("storage_used_percent"),
            storage_free_bytes=telemetry.get("storage_free_bytes"),
            power_watts=telemetry.get("power_watts"),
            extra_data=extra_json,
        )
        db.add(snapshot)
        db.commit()
    except Exception as e:
        logger.debug(f"Échec enregistrement télémétrie snapshot: {e}")
        try:
            db.rollback()
        except Exception:
            pass


def purge_expired_logs_and_metrics(db, retention_days: int = 7) -> dict[str, int]:
    """Supprime les logs d'activité et métriques système plus anciens que retention_days."""
    from app.models import ActivityLog, SystemMetricsHistory
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, retention_days))
    purged_logs = 0
    purged_metrics = 0
    try:
        purged_logs = db.query(ActivityLog).filter(ActivityLog.timestamp < cutoff).delete()
        purged_metrics = db.query(SystemMetricsHistory).filter(SystemMetricsHistory.timestamp < cutoff).delete()
        db.commit()
        if purged_logs > 0 or purged_metrics > 0:
            logger.info(f"Purge automatique réussie ({retention_days}j) : {purged_logs} logs et {purged_metrics} métriques supprimés.")
    except Exception as e:
        logger.error(f"Erreur purge logs/métriques: {e}")
        try:
            db.rollback()
        except Exception:
            pass
    return {"purged_logs": purged_logs, "purged_metrics": purged_metrics}

