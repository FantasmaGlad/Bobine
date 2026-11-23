"""Extensions acceptées à l'import (vidéos, fonds)."""
from pathlib import Path
from app.utils import media_formats


SUPPORTED_EXTENSIONS = media_formats.VIDEO


IMAGE_EXTENSIONS = media_formats.BACKGROUND_IMAGE_SOURCES


BACKGROUND_SUPPORTED_EXTENSIONS = media_formats.BACKGROUND_VIDEO | IMAGE_EXTENSIONS


def is_image_background(file_path: str) -> bool:
    """Fond image fixe ou animée, reconnu à l'extension du fichier enregistré (les formats convertis sont stockés en WebP)."""
    return Path(file_path).suffix.lower() in media_formats.BACKGROUND_IMAGE
