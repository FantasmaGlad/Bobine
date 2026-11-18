import glob
import logging
import os
import time

from ..cpu import get_cpu_percent
from .estimate import laptop_on_ac_watts

logger = logging.getLogger("app.hardware.power")

_LAST_RAPL_CHECK = 0.0
_LAST_RAPL_ENERGY_UJ = 0


def hwmon_power() -> float | None:
    for h_dir in glob.glob("/sys/class/hwmon/hwmon*"):
        name_file = os.path.join(h_dir, "name")
        name = ""
        if os.path.exists(name_file):
            try:
                with open(name_file, "r", encoding="utf-8") as f:
                    name = f.read().strip().lower()
            except Exception as exc:
                logger.debug("_linux_hwmon_power : %s", exc)
        if "bat" in name or "battery" in name:
            continue

        for p in glob.glob(os.path.join(h_dir, "power*_input")) + glob.glob(os.path.join(h_dir, "power*_average")):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    val = int(f.read().strip())
                    if 500_000 <= val <= 500_000_000:
                        return round(val / 1_000_000.0, 1)
            except Exception as exc:
                logger.debug("_linux_hwmon_power : %s", exc)
    return None


def rapl_power() -> float | None:
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
        except Exception as exc:
            logger.debug("_linux_rapl_power : %s", exc)
    return None


def _on_ac() -> bool:
    for ac_dir in glob.glob("/sys/class/power_supply/*"):
        type_file = os.path.join(ac_dir, "type")
        online_file = os.path.join(ac_dir, "online")
        if os.path.exists(type_file) and os.path.exists(online_file):
            try:
                t = open(type_file, "r").read().strip().lower()
                o = open(online_file, "r").read().strip()
                if t in ("mains", "ac", "usb") and o == "1":
                    return True
            except Exception as exc:
                logger.debug("_linux_on_ac : %s", exc)
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
        except Exception as exc:
            logger.debug("_battery_watts : %s", exc)
    elif os.path.exists(curr_file) and os.path.exists(volt_file):
        try:
            c = int(open(curr_file, "r").read().strip())
            v = int(open(volt_file, "r").read().strip())
            if c > 0 and v > 0:
                return (c * v) / 1_000_000_000_000.0
        except Exception as exc:
            logger.debug("_battery_watts : %s", exc)
    return None


def battery_power() -> float | None:
    is_on_ac = _on_ac()
    for bat_dir in glob.glob("/sys/class/power_supply/*"):
        type_file = os.path.join(bat_dir, "type")
        if os.path.exists(type_file):
            try:
                if open(type_file, "r").read().strip().lower() != "battery":
                    continue
            except Exception as exc:
                logger.debug("_linux_battery_power : %s", exc)

        status_file = os.path.join(bat_dir, "status")
        status = ""
        if os.path.exists(status_file):
            try:
                status = open(status_file, "r").read().strip().lower()
            except Exception as exc:
                logger.debug("_linux_battery_power : %s", exc)

        bat_watts = _battery_watts(bat_dir)

        if status == "discharging" and bat_watts and bat_watts >= 0.5:
            return round(bat_watts, 1)

        if status in ("charging", "full", "not charging") or is_on_ac:
            base_laptop_w = laptop_on_ac_watts(get_cpu_percent())
            if status == "charging" and bat_watts and bat_watts > 1.0:
                return round(bat_watts + base_laptop_w, 1)
            return round(base_laptop_w, 1)
    return None


def probes():
    return [hwmon_power, rapl_power, battery_power]
