import logging
import os

import psutil

from ..cpu import get_cpu_percent
from ..platforms import first_answer

logger = logging.getLogger("app.hardware.power")


def _desktops():
    from . import macos, windows
    return {"macos": macos, "windows": windows}


def laptop_on_ac_watts(cpu_pct: float) -> float:
    return 9.0 + (cpu_pct / 100.0) * 22.0


def estimated_power() -> float | None:
    cpu_pct = get_cpu_percent()
    nb_cores = os.cpu_count() or 4

    bat = None
    try:
        bat = psutil.sensors_battery()
    except Exception as exc:
        logger.debug("_estimated_power : %s", exc)

    if bat is not None:
        if not bat.power_plugged:
            base_discharge = 6.0 + (cpu_pct / 100.0) * (nb_cores * 1.8)
            return round(min(65.0, max(3.0, base_discharge)), 1)
        base_laptop_ac = laptop_on_ac_watts(cpu_pct)
        if hasattr(bat, "percent") and bat.percent is not None and bat.percent < 90:
            charge_power = 25.0
            return round(min(120.0, max(12.0, base_laptop_ac + charge_power)), 1)
        return round(min(65.0, max(7.0, base_laptop_ac)), 1)

    desktop = first_answer(_desktops(), lambda implementation: implementation.desktop_watts(cpu_pct, nb_cores))
    if desktop:
        return desktop
    base_mini = min(12.0, max(4.0, nb_cores * 1.2))
    active_mini = base_mini + (cpu_pct / 100.0) * (nb_cores * 2.5)
    return round(min(90.0, max(3.5, active_mini)), 1)
