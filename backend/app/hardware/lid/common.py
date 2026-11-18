import logging

import psutil

COMMAND_TIMEOUT_SECONDS = 10

logger = logging.getLogger("app.hardware.lid")


def has_battery() -> bool:
    try:
        return psutil.sensors_battery() is not None
    except Exception as exc:
        logger.debug("_has_laptop_lid : %s", exc)
        return False
