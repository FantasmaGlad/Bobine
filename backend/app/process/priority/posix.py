import logging
import os

logger = logging.getLogger(__name__)


def popen_kwargs() -> dict:
    return {}


def lower(pid: int) -> None:
    try:
        os.setpriority(os.PRIO_PROCESS, pid, 10)
    except (OSError, AttributeError) as e:
        logger.debug(f"Priorité réduite de ffmpeg impossible (pid {pid}) : {e}")
