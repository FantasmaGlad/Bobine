"""Extensions acceptées à l'import (vidéos, fonds)."""
from pathlib import Path
from app.utils import media_formats


SUPPORTED_EXTENSIONS = media_formats.VIDEO


# Fonds animés : mêmes conteneurs que les cours, plus WebM (nativement
# lisible par Chromium, format courant pour des boucles d'ambiance courtes).
# Images fixes : un fond
# n'a plus besoin d'être une boucle vidéo — png/jpg/webp couvrent l'essentiel
# des visuels de marque déjà utilisés ailleurs dans l'appli (logo, etc.).
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


BACKGROUND_SUPPORTED_EXTENSIONS = SUPPORTED_EXTENSIONS | {".webm"} | IMAGE_EXTENSIONS


def is_image_background(file_path: str) -> bool:
    """Détecte un fond image fixe par extension — pas de colonne dédiée en base, la distinction ne sert qu'à
    orienter le pipeline d'import et le rendu (image vs boucle vidéo)."""
    return Path(file_path).suffix.lower() in IMAGE_EXTENSIONS
