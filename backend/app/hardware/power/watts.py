import logging
from typing import Callable

from ..platforms import detected
from . import android, linux, macos
from .estimate import estimated_power

logger = logging.getLogger("app.hardware.power")


def _power_probes() -> list[Callable[[], float | None]]:
    platforms = detected()
    probes: list[Callable[[], float | None]] = []
    if "android" in platforms:
        probes.append(android.battery_power)
    elif "linux" in platforms:
        probes += linux.probes()
    if "macos" in platforms:
        probes.append(macos.battery_power)
    probes.append(estimated_power)
    return probes


def get_power_watts() -> float | None:
    """Consommation instantanée de la machine en watts, ou `None` si aucune sonde ne répond."""
    for probe in _power_probes():
        try:
            watts = probe()
        except Exception as exc:
            logger.debug("Sonde de puissance %s en échec : %s", probe.__name__, exc)
            continue
        if watts is not None:
            return watts
    return None
