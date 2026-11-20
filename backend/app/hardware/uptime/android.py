import logging

logger = logging.getLogger(__name__)


def system_uptime() -> int:
    try:
        from android.os import SystemClock
        return int(SystemClock.elapsedRealtime() / 1000)
    except Exception as exc:
        logger.debug("get_runtime_info : %s", exc)
        return 0
