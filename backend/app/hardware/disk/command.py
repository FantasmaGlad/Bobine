import logging
import subprocess

logger = logging.getLogger(__name__)


def first_line(command: list[str], timeout: float, select=lambda line: line) -> str:
    """Première ligne utile de la sortie d'une commande ; vide si elle échoue."""
    try:
        out = subprocess.check_output(command, text=True, timeout=timeout)
    except Exception as exc:
        logger.debug("get_storage_model : %s", exc)
        return ""
    return next((value for value in (select(line) for line in out.splitlines()) if value), "")
