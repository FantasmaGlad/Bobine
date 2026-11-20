import logging
import os

logger = logging.getLogger(__name__)


def system_uptime() -> int:
    if not os.path.exists("/proc/uptime"):
        return 0
    try:
        with open("/proc/uptime", "r", encoding="utf-8") as f:
            return int(float(f.read().split()[0]))
    except Exception as exc:
        logger.debug("get_runtime_info : %s", exc)
        return 0
