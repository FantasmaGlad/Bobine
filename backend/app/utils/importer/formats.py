"""Extensions acceptées à l'import (vidéos, fonds)."""
from pathlib import Path
from app.utils import media_formats


SUPPORTED_EXTENSIONS = media_formats.VIDEO


IMAGE_EXTENSIONS = media_formats.IMAGE


BACKGROUND_SUPPORTED_EXTENSIONS = SUPPORTED_EXTENSIONS | {".webm"} | IMAGE_EXTENSIONS


def is_image_background(file_path: str) -> bool:
    """Détecte un fond image fixe par extension — pas de colonne dédiée en base, la distinction ne sert qu'à orienter le pipeline d'import et le rendu (image vs boucle vidéo)."""
    return Path(file_path).suffix.lower() in IMAGE_EXTENSIONS
