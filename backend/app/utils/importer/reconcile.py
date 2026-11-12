"""Rapprochement au démarrage des fichiers de médias et de la base."""
import logging
from pathlib import Path
from app.config import settings
from app.database import SessionLocal
from app.models import Background, Video


logger = logging.getLogger(__name__)


def reconcile_orphaned_media() -> None:
    """Filet de sécurité au démarrage : import_video/import_background déplacent déjà le fichier vers son dossier final AVANT le commit DB, avec un nettoyage sur exception Python (`except Exception as dbe`) — mais un crash DUR du processus (coupure électrique, kill -9) entre les deux n'est pas une exception Python à rattraper, et peut laisser un fichier à son emplacement final sans plus aucune ligne DB pour le référencer."""
    db = SessionLocal()
    try:
        known_video_paths = {row[0] for row in db.query(Video.file_path).all()}
        known_background_paths = {row[0] for row in db.query(Background.file_path).all()}
    finally:
        db.close()

    for directory, known_paths in (
        (Path(settings.media_dir), known_video_paths),
        (Path(settings.backgrounds_dir), known_background_paths),
    ):
        if not directory.is_dir():
            continue
        for entry in directory.iterdir():
            if not entry.is_file():
                continue
            if entry.name.startswith("temp_"):
                try:
                    entry.unlink()
                    logger.warning(f"Fichier temporaire orphelin nettoyé au démarrage : {entry}")
                except OSError as e:
                    logger.error(f"Impossible de nettoyer le fichier temporaire orphelin {entry}: {e}")
                continue
            if str(entry) not in known_paths:
                logger.warning(
                    f"Fichier orphelin détecté (aucune ligne en base ne le référence) : {entry} — "
                    "probablement laissé par un arrêt brutal du service pendant un import. "
                    "À vérifier/nettoyer manuellement."
                )
