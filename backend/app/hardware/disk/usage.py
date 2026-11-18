import logging
import shutil
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def get_storage_usage() -> dict[str, Any]:
    """Mesure l'espace disque réel sur le dossier média applicatif (et non sur / qui est un ramdisk système de 700 Mo en lecture seule sous Android)."""
    try:
        from app.config import runtime_settings
        media_dir = Path(runtime_settings.media_dir)
    except Exception:
        media_dir = Path("data")

    probe = media_dir
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    if not probe.exists():
        probe = Path(".")

    try:
        usage = shutil.disk_usage(probe)
        used_pct = round((usage.used / usage.total) * 100, 1) if usage.total else 0.0
        return {
            "total_bytes": usage.total,
            "used_bytes": usage.used,
            "free_bytes": usage.free,
            "used_percent": used_pct,
        }
    except Exception as exc:
        logger.warning("Espace disque illisible : %s", exc)
        return {"total_bytes": 0, "used_bytes": 0, "free_bytes": 0, "used_percent": 0.0}
