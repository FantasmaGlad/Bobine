import logging
import subprocess
from typing import Callable

logger = logging.getLogger("app.hardware.gpu")


def probe(read: Callable[[], object]):
    try:
        return read()
    except Exception as exc:
        logger.debug("get_gpu_info : %s", exc)
        return None


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read().strip()


def output(command: list[str], timeout: float = 1) -> str:
    return subprocess.check_output(command, text=True, timeout=timeout)
