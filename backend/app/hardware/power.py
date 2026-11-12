"""Consommation électrique instantanée et énergie cumulée depuis le démarrage."""

import glob
import os
import subprocess
import sys
import time
from typing import Callable

import psutil

from .cpu import get_cpu_percent
from .probe import _SERVICE_START_TIME, is_android_system

_LAST_RAPL_CHECK = 0.0
_LAST_RAPL_ENERGY_UJ = 0


_CUMULATIVE_ENERGY_WH: float = 0.0
_LAST_ENERGY_SAMPLE_TIME: float = 0.0


def _android_power() -> float | None:
    from android.content import Context, Intent, IntentFilter
    from android.os import BatteryManager
    from com.chaquo.python import Python
    app_ctx = Python.getPlatform().getApplication()
    bm = app_ctx.getSystemService(Context.BATTERY_SERVICE)
    filt = IntentFilter(Intent.ACTION_BATTERY_CHANGED)
    intent = app_ctx.registerReceiver(None, filt)
    if not intent:
        return None
    plugged = intent.getIntExtra(BatteryManager.EXTRA_PLUGGED, 0)
    status = intent.getIntExtra(BatteryManager.EXTRA_STATUS, -1)
    voltage_mv = intent.getIntExtra(BatteryManager.EXTRA_VOLTAGE, -1)
    current_ua = bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CURRENT_NOW)
    if current_ua == -2147483648:
        current_ua = 0

    cpu_pct = get_cpu_percent()

    if plugged > 0 or status in (BatteryManager.BATTERY_STATUS_CHARGING, BatteryManager.BATTERY_STATUS_FULL):
        active_w = 3.2 + (cpu_pct / 100.0) * 5.0

        if status == BatteryManager.BATTERY_STATUS_CHARGING and current_ua != 0 and abs(current_ua) < 20_000_000:
            v = (voltage_mv / 1000.0) if voltage_mv > 0 else 4.2
            charge_w = (abs(current_ua) / 1_000_000.0) * v
            return round(min(120.0, max(1.0, charge_w + active_w)), 1)
        return round(min(60.0, max(1.5, active_w)), 1)

    if current_ua != 0 and abs(current_ua) < 20_000_000 and voltage_mv > 0:
        watts = (abs(current_ua) / 1_000_000.0) * (voltage_mv / 1000.0)
        if 0.5 <= watts <= 60.0:
            return round(watts, 1)

    return round(2.8 + (cpu_pct / 100.0) * 4.5, 1)


def _linux_hwmon_power() -> float | None:
    for h_dir in glob.glob("/sys/class/hwmon/hwmon*"):
        name_file = os.path.join(h_dir, "name")
        name = ""
        if os.path.exists(name_file):
            try:
                with open(name_file, "r", encoding="utf-8") as f:
                    name = f.read().strip().lower()
            except Exception:
                pass
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
    return None


def _linux_rapl_power() -> float | None:
    global _LAST_RAPL_CHECK, _LAST_RAPL_ENERGY_UJ
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


def _linux_on_ac() -> bool:
    for ac_dir in glob.glob("/sys/class/power_supply/*"):
        type_file = os.path.join(ac_dir, "type")
        online_file = os.path.join(ac_dir, "online")
        if os.path.exists(type_file) and os.path.exists(online_file):
            try:
                t = open(type_file, "r").read().strip().lower()
                o = open(online_file, "r").read().strip()
                if t in ("mains", "ac", "usb") and o == "1":
                    return True
            except Exception:
                pass
    return False


def _battery_watts(bat_dir: str) -> float | None:
    power_file = os.path.join(bat_dir, "power_now")
    curr_file = os.path.join(bat_dir, "current_now")
    volt_file = os.path.join(bat_dir, "voltage_now")
    if os.path.exists(power_file):
        try:
            val = int(open(power_file, "r").read().strip())
            if val > 0:
                return val / 1_000_000.0
        except Exception:
            pass
    elif os.path.exists(curr_file) and os.path.exists(volt_file):
        try:
            c = int(open(curr_file, "r").read().strip())
            v = int(open(volt_file, "r").read().strip())
            if c > 0 and v > 0:
                return (c * v) / 1_000_000_000_000.0
        except Exception:
            pass
    return None


def _linux_battery_power() -> float | None:
    is_on_ac = _linux_on_ac()
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

        bat_watts = _battery_watts(bat_dir)

        if status == "discharging" and bat_watts and bat_watts >= 0.5:
            return round(bat_watts, 1)

        if status in ("charging", "full", "not charging") or is_on_ac:
            base_laptop_w = _laptop_on_ac_watts(get_cpu_percent())
            if status == "charging" and bat_watts and bat_watts > 1.0:
                return round(bat_watts + base_laptop_w, 1)
            return round(base_laptop_w, 1)
    return None


def _macos_power() -> float | None:
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

    base_mac_w = 4.5 + (get_cpu_percent() / 100.0) * 22.0

    if external_connected:
        if is_charging and amp and amp > 0 and volt and volt > 0:
            return round((volt * amp) / 1_000_000.0 + base_mac_w, 1)
        return round(base_mac_w, 1)
    if volt and amp and volt > 0 and amp != 0:
        watts = (volt * abs(amp)) / 1_000_000.0
        if 0.5 <= watts <= 150.0:
            return round(watts, 1)
    return None


def _laptop_on_ac_watts(cpu_pct: float) -> float:
    return 9.0 + (cpu_pct / 100.0) * 22.0


def _estimated_power() -> float | None:
    cpu_pct = get_cpu_percent()
    nb_cores = os.cpu_count() or 4

    bat = None
    try:
        bat = psutil.sensors_battery()
    except Exception:
        pass

    if bat is not None:
        if not bat.power_plugged:
            base_discharge = 6.0 + (cpu_pct / 100.0) * (nb_cores * 1.8)
            return round(min(65.0, max(3.0, base_discharge)), 1)
        base_laptop_ac = _laptop_on_ac_watts(cpu_pct)
        if hasattr(bat, "percent") and bat.percent is not None and bat.percent < 90:
            charge_power = 25.0
            return round(min(120.0, max(12.0, base_laptop_ac + charge_power)), 1)
        return round(min(65.0, max(7.0, base_laptop_ac)), 1)

    if sys.platform == "win32":
        base_desktop = 28.0 + min(25.0, max(0.0, (nb_cores - 4) * 2.5))
        active_desktop = base_desktop + (cpu_pct / 100.0) * (nb_cores * 4.5)
        return round(min(450.0, max(20.0, active_desktop)), 1)
    if sys.platform == "darwin":
        base_macmini = 6.5 + min(8.0, max(0.0, (nb_cores - 4) * 1.0))
        active_macmini = base_macmini + (cpu_pct / 100.0) * (nb_cores * 3.0)
        return round(min(120.0, max(5.0, active_macmini)), 1)
    base_mini = min(12.0, max(4.0, nb_cores * 1.2))
    active_mini = base_mini + (cpu_pct / 100.0) * (nb_cores * 2.5)
    return round(min(90.0, max(3.5, active_mini)), 1)


def _power_probes() -> list[Callable[[], float | None]]:
    probes: list[Callable[[], float | None]] = []
    if is_android_system():
        probes.append(_android_power)
    elif sys.platform.startswith("linux"):
        probes += [_linux_hwmon_power, _linux_rapl_power, _linux_battery_power]
    if sys.platform == "darwin":
        probes.append(_macos_power)
    probes.append(_estimated_power)
    return probes


def get_power_watts() -> float | None:
    """Consommation instantanée de la machine en watts, ou `None` si aucune sonde ne répond."""
    for probe in _power_probes():
        try:
            watts = probe()
        except Exception:
            continue
        if watts is not None:
            return watts
    return None


def update_cumulative_energy(watts: float | None) -> None:
    """Met à jour l'énergie cumulée en Watt-heures (Wh)."""
    global _CUMULATIVE_ENERGY_WH, _LAST_ENERGY_SAMPLE_TIME
    now = time.time()
    if _LAST_ENERGY_SAMPLE_TIME > 0 and watts and watts > 0:
        delta_hours = (now - _LAST_ENERGY_SAMPLE_TIME) / 3600.0
        if 0 < delta_hours < 0.1:
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
