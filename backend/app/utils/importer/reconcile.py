"""Rapprochement au démarrage des fichiers de médias et de la base."""
import logging
from pathlib import Path
from app.config import settings
from app.database import SessionLocal
from app.models import Video


logger = logging.getLogger(__name__)


def reconcile_orphaned_media() -> None:
    """Filet de sécurité au démarrage : import_video/import_asset déplacent déjà le fichier vers son dossier final AVANT le commit DB, avec un nettoyage sur exception Python."""
    from app.media_assets.registry import COLLECTIONS

    db = SessionLocal()
    try:
        folders = [(Path(settings.media_dir), {row[0] for row in db.query(Video.file_path).all()})]
        folders += [(Path(c.directory()), {row[0] for row in db.query(c.model.file_path).all()}) for c in COLLECTIONS]
    finally:
        db.close()

    for directory, known_paths in folders:
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
