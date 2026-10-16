import os
import re
import uuid
from pathlib import Path

from app.config import settings

LANGUAGE_MAP: dict[str, str] = {
    "fr": "Français",
    "fra": "Français",
    "fre": "Français",
    "en": "English",
    "eng": "English",
    "es": "Español",
    "esp": "Español",
    "spa": "Español",
    "de": "Deutsch",
    "deu": "Deutsch",
    "ger": "Deutsch",
    "it": "Italiano",
    "ita": "Italiano",
    "pt": "Português",
    "por": "Português",
    "nl": "Nederlands",
    "nld": "Nederlands",
}


def detect_language_from_filename(filename: str) -> tuple[str, str]:
    """Détecte le code et libellé de langue depuis le nom de fichier (ex: course.fr.srt, film.en.vtt)."""
    clean_name = filename.lower()
    # Recherche d'un suffixe de langue avant l'extension .srt ou .vtt
    match = re.search(r"[._-]([a-z]{2,3})\.(?:srt|vtt)$", clean_name)
    if match:
        code = match.group(1)
        if code in LANGUAGE_MAP:
            standard_code = "fr" if code in ("fra", "fre") else ("en" if code == "eng" else ("es" if code in ("esp", "spa") else ("de" if code in ("deu", "ger") else code)))
            return standard_code, LANGUAGE_MAP[code]
    return "fr", "Français"


def convert_srt_to_vtt(content: str) -> str:
    """Convertit une chaîne SRT en format WebVTT standard."""
    text = content.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    if text.strip().startswith("WEBVTT"):
        return text

    # Remplacement des virgules des millisecondes par des points dans les repères temporels
    # Format SRT : 00:01:20,500 --> 00:01:23,100
    # Format VTT : 00:01:20.500 --> 00:01:23.100
    converted = re.sub(r"(\d{2}:\d{2}:\d{2}),(\d{3})", r"\1.\2", text)
    return f"WEBVTT\n\n{converted.strip()}\n"


def get_subtitles_directory() -> Path:
    """Renvoie le répertoire de stockage des sous-titres, créé s'il n'existe pas."""
    target = Path(settings.subtitles_dir)
    target.mkdir(parents=True, exist_ok=True)
    return target
