import logging
from pathlib import Path

logger = logging.getLogger("app.config")


def ensure_dir(target: Path) -> Path:
    try:
        target.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        logger.debug("_data_root : %s", exc)
    return target
