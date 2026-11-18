import glob
import logging

from ..probe import shutil_which
from .command import first_line

logger = logging.getLogger(__name__)


def storage_model() -> str:
    for path in glob.glob("/sys/block/*/device/model"):
        if any(x in path for x in ("loop", "ram", "zram")):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                value = f.read().strip()
            if value:
                return value
        except Exception as exc:
            logger.debug("get_storage_model : %s", exc)
    if shutil_which("lsblk"):
        return first_line(["lsblk", "-d", "-n", "-o", "MODEL"], 1, str.strip)
    return ""
