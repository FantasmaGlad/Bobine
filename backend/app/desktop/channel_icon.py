"""Icône de la barre système (tray) selon le canal de mise à jour choisi.

Logique pure, sans réseau ni affichage : tout ce qui touche au système (appel HTTP,
fichiers) est injecté, ce qui la rend testable (backend/tests/test_channel_icon.py).
`app.desktop.tray` fournit les entrées réelles.

Deux notions de canal coexistent et ne doivent pas être confondues :
  - le canal CHOISI par l'utilisateur (réglage `update_channel`, modifiable à chaud) : il
    pilote ce module, donc l'icône de la barre système, le logo de l'interface, le favicon
    et l'écran de démarrage Android ;
  - le canal du BUILD installé (suffixe de `VERSION`, cf. `app.utils.version.build_channel_of_version`) :
    il fixe l'icône du lanceur, de l'installeur et de l'exécutable, décidée à la construction
    (packaging/common/channel.py, packaging/common/channel.sh).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from pathlib import Path

from PIL import Image

from app.utils.version import DEFAULT_RELEASE_CHANNEL, normalize_release_channel

logger = logging.getLogger(__name__)

# Icône « sans canal » : Stable, aussi dernier recours quand l'icône du canal est introuvable.
DEFAULT_ICON_FILENAME = "logo_bobine_icon.png"

# Canal écrit UNE SEULE FOIS par install.sh (Linux) : indice de dernier recours quand le
# backend ne répond pas encore, jamais une source de vérité (il n'est pas mis à jour quand
# l'utilisateur change de canal dans les Réglages).
INSTALL_CHANNEL_HINT = Path("/etc/bobine/update-channel")

TRAY_ICON_SIZE = 64


def channel_icon_filename(channel: str) -> str:
    return f"logo_bobine_icon_{channel}.png"


def detect_channel(
    fetch_settings: Callable[[], dict | None],
    hint_file: Path = INSTALL_CHANNEL_HINT,
) -> str:
    """Canal choisi : réglage du backend en premier (source de vérité), puis indice
    d'installation, puis Stable. Ne lève jamais : la barre système ne doit pas dépendre
    de l'état du backend."""
    try:
        settings = fetch_settings()
    except Exception as exc:  # backend pas prêt, redémarrage, port occupé...
        logger.debug("Canal de mise à jour illisible via l'API : %s", exc)
        settings = None
    channel = normalize_release_channel((settings or {}).get("update_channel"))
    if channel:
        return channel
    try:
        channel = normalize_release_channel(hint_file.read_text(encoding="utf-8"))
    except OSError:
        channel = None
    return channel or DEFAULT_RELEASE_CHANNEL


def icon_candidates(channel: str, exe_dir: Path, images_dir: Path) -> list[Path]:
    """Emplacements essayés dans l'ordre : à côté de l'exécutable (Windows/Linux figés,
    `contents_directory="."`), `Contents/Resources/` (bundle macOS), puis le dépôt en
    développement ; l'icône du canal avant l'icône par défaut à chaque emplacement."""
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
    """Première image lisible parmi `candidates`, sinon un carré uni (la barre système
    doit toujours avoir une icône, même dans une installation incomplète)."""
    for path in candidates:
        if not path.exists():
            continue
        try:
            return _square_thumbnail(path, size)
        except Exception as exc:
            logger.warning("Icône de barre système illisible (%s) : %s", path, exc)
    logger.warning("Aucune icône de barre système trouvée pour le canal %s : icône de repli", channel)
    return Image.new("RGBA", (size, size), (15, 110, 116, 255))
