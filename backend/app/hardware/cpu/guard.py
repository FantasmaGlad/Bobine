import logging

logger = logging.getLogger(__name__)


def guarded(read) -> str:
    try:
        return read()
    except Exception as exc:
        logger.debug("get_cpu_model_name : %s", exc)
        return ""
