"""Icône de la barre système (tray) selon le canal de mise à jour choisi."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from pathlib import Path

from PIL import Image

from app import release_channel

logger = logging.getLogger(__name__)

DEFAULT_ICON_FILENAME = "logo_bobine_icon.png"

TRAY_ICON_SIZE = 64


def channel_icon_filename(channel: str) -> str:
    return f"logo_bobine_icon_{channel}.png"


def detect_channel(
    fetch_settings: Callable[[], dict | None],
    hint_file: Path = release_channel.INSTALL_HINT_PATH,
) -> str:
    """Canal choisi : réglage du backend en premier (source de vérité : choix explicite ou, à défaut, canal d'installation), puis, backend injoignable, le canal d'installation du build (`release_channel.install_channel`)."""
    try:
        settings = fetch_settings()
    except Exception as exc:
        logger.debug("Canal de mise à jour illisible via l'API : %s", exc)
        settings = None
    channel = release_channel.normalize((settings or {}).get("update_channel"))
    return channel or release_channel.install_channel(hint_file=hint_file)


def icon_candidates(channel: str, exe_dir: Path, images_dir: Path) -> list[Path]:
    """Emplacements essayés dans l'ordre : à côté de l'exécutable (Windows/Linux figés, `contents_directory="."`), `Contents/Resources/` (bundle macOS), puis le dépôt en développement ; l'icône du canal avant l'icône par défaut à chaque emplacement."""
    names = [channel_icon_filename(channel), DEFAULT_ICON_FILENAME]
    roots = [exe_dir, exe_dir.parent / "Resources", images_dir]
    return [root / name for root in roots for name in names]


def _square_thumbnail(path: Path, size: int) -> Image.Image:
    image = Image.open(path).convert("RGBA")
    bbox = image.getbbox()
    cropped = image.crop(bbox) if bbox else image
    side = max(cropped.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(cropped, ((side - cropped.width) // 2, (side - cropped.height) // 2))
    return square.resize((size, size), Image.Resampling.LANCZOS)


def load_tray_image(channel: str, candidates: Iterable[Path], size: int = TRAY_ICON_SIZE) -> Image.Image:
    """Première image lisible parmi `candidates`, sinon un carré uni (la barre système doit toujours avoir une icône, même dans une installation incomplète)."""
    for path in candidates:
        if not path.exists():
            continue
        try:
            return _square_thumbnail(path, size)
        except Exception as exc:
            logger.warning("Icône de barre système illisible (%s) : %s", path, exc)
    logger.warning("Aucune icône de barre système trouvée pour le canal %s : icône de repli", channel)
    return Image.new("RGBA", (size, size), (15, 110, 116, 255))
