import logging
from typing import Any, Callable

logger = logging.getLogger("app.hardware.memory")


def probe(read: Callable[[], Any]) -> Any:
    try:
        return read()
    except Exception as exc:
        logger.debug("get_ram_info : %s", exc)
        return None
