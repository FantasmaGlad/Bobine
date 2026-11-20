import time

import psutil

from ..platforms import first_answer
from . import android, linux

_IMPLEMENTATIONS = {"android": android, "linux": linux}


def system_uptime_seconds(service_uptime: int) -> int:
    """Durée depuis le démarrage de la machine ; à défaut, celle du service."""
    uptime = first_answer(_IMPLEMENTATIONS, lambda implementation: max(0, implementation.system_uptime()))
    if uptime:
        return uptime
    try:
        return int(time.time() - psutil.boot_time())
    except Exception:
        return service_uptime
