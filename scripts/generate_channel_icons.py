#!/usr/bin/env python3
"""Génère toutes les icônes dérivées des icônes de canal (Stable, Bêta, Canary).

Source de vérité unique : `Assets/Images/channel-icons/bobine-channel-<canal>.png`
(512 x 512, RGBA, fond transparent) et `banner-wordmark.png` (texte « obine » de la
bannière Android TV). Tout le reste est DÉRIVÉ et ne se modifie jamais à la main :
relancer ce script. Le guide complet (ajouter un canal, ajouter une cible) est dans
`Assets/Images/channel-icons/README.md`.

    python3 scripts/generate_channel_icons.py            # écrit tous les fichiers
    python3 scripts/generate_channel_icons.py --check    # échoue si un fichier est périmé
    python3 scripts/generate_channel_icons.py --list     # liste les fichiers produits

Principe de câblage (détail dans le README ci-dessus) :
  - icône de lanceur / d'installeur / d'exécutable : fixée À LA CONSTRUCTION par le
    canal du build (suffixe de `VERSION` : `-beta`, `-canary`, sinon Stable) ;
  - icônes affichées dans l'application (barre système, logo, favicon, écran de
    démarrage) : suivent le canal choisi à l'exécution.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops

REPO_DIR = Path(__file__).resolve().parent.parent
SOURCE_DIR = REPO_DIR / "Assets" / "Images" / "channel-icons"

# Liste des canaux : le registre unique backend/app/release_channel.py (chargé par son chemin,
# sans importer le backend). Ajouter un canal commence là-bas.
_spec = importlib.util.spec_from_file_location("bobine_release_channel", REPO_DIR / "backend" / "app" / "release_channel.py")
_registry = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _registry  # requis par @dataclass
_spec.loader.exec_module(_registry)
CHANNELS = _registry.CHANNEL_IDS
DEFAULT_CHANNEL = _registry.DEFAULT_CHANNEL

# Cadrage : part du carré occupée par la plus grande dimension du dessin.
FULL_FILL = 0.90        # icônes de bureau (hicolor, ico, icns, tray)
ADAPTIVE_FILL = 0.572   # calque avant d'une icône adaptative Android (zone de sécurité 66/108 dp)

LINUX_SIZES = (16, 24, 32, 48, 64, 128, 256, 512)
LINUX_PIXMAP_SIZE = 256
ICO_SIZES = [(s, s) for s in (16, 24, 32, 48, 64, 128, 256)]
ICNS_CANVAS = 1024
TRAY_SIZE = 256
FAVICON_SIZE = 64
ASSISTANT_SIZE = 160
VERSIONS_SIZE = 1024
SPLASH_SIZE = 512

# Densités Android -> facteur appliqué à la grille de 108 dp d'une icône adaptative.
ANDROID_DENSITIES = {"mdpi": 1.0, "hdpi": 1.5, "xhdpi": 2.0, "xxhdpi": 3.0, "xxxhdpi": 4.0}

# Bannière Android TV (16:9) : emplacement de l'icône qui tient lieu de « B » du mot
# « Bobine », et du reste du mot (raster conservé tel quel dans `banner-wordmark.png`).
BANNER_SIZE = (640, 360)
BANNER_ICON_BOX = (54, 87, 156, 186)        # x, y, largeur, hauteur
BANNER_WORDMARK_ORIGIN = (212, 132)



@dataclass(frozen=True)
class Output:
    """Un fichier produit : chemin relatif au dépôt, image, format."""

    path: str
    image: Image.Image
    fmt: str = "PNG"


def master_path(channel: str) -> Path:
    return SOURCE_DIR / f"bobine-channel-{channel}.png"


def load_master(channel: str) -> Image.Image:
    path = master_path(channel)
    if not path.exists():
        raise FileNotFoundError(f"Icône source absente : {path.relative_to(REPO_DIR)}")
    image = Image.open(path).convert("RGBA")
    if image.size != (512, 512):
        raise ValueError(f"{path.name} doit mesurer 512 x 512 (trouvé {image.size[0]} x {image.size[1]})")
    return image


def fit_on_square(source: Image.Image, size: int, fill: float) -> Image.Image:
    """Recadre le dessin sur sa boîte englobante, le met à l'échelle sans déformation
    (plus grande dimension = `fill` x `size`) et le centre sur un carré transparent."""
    bbox = source.getbbox()
    art = source.crop(bbox) if bbox else source
    scale = (size * fill) / max(art.size)
    width, height = max(1, round(art.width * scale)), max(1, round(art.height * scale))
    art = art.resize((width, height), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(art, ((size - width) // 2, (size - height) // 2), art)
    return canvas


def resized(image: Image.Image, size: int) -> Image.Image:
    return image.resize((size, size), Image.Resampling.LANCZOS)


def tv_banner(channel_master: Image.Image) -> Image.Image:
    """Bannière Leanback : icône du canal à la place du « B » + mot « obine » d'origine."""
    wordmark_path = SOURCE_DIR / "banner-wordmark.png"
    if not wordmark_path.exists():
        raise FileNotFoundError(f"Source absente : {wordmark_path.relative_to(REPO_DIR)}")
    banner = Image.new("RGBA", BANNER_SIZE, (0, 0, 0, 0))
    x, y, width, height = BANNER_ICON_BOX
    bbox = channel_master.getbbox()
    art = channel_master.crop(bbox) if bbox else channel_master
    scale = min(width / art.width, height / art.height)
    art = art.resize((max(1, round(art.width * scale)), max(1, round(art.height * scale))), Image.Resampling.LANCZOS)
    banner.paste(art, (x + (width - art.width) // 2, y + (height - art.height) // 2), art)
    wordmark = Image.open(wordmark_path).convert("RGBA")
    banner.paste(wordmark, BANNER_WORDMARK_ORIGIN, wordmark)
    return banner


def outputs_for_channel(channel: str) -> list[Output]:
    master = load_master(channel)
    desktop = fit_on_square(master, 1024, FULL_FILL)
    outputs: list[Output] = []

    # Linux (FHS) : une image par taille, installée sous deux noms par les scripts de
    # paquetage (cf. packaging/common/channel.sh).
    linux_root = f"packaging/linux/icons/{channel}"
    for size in LINUX_SIZES:
        outputs.append(Output(f"{linux_root}/hicolor/{size}x{size}/apps/com.bobine.app.png", resized(desktop, size)))
    outputs.append(Output(f"{linux_root}/pixmaps/com.bobine.app.png", resized(desktop, LINUX_PIXMAP_SIZE)))

    # Windows et macOS : icône d'exécutable / d'installeur / de bundle.
    outputs.append(Output(f"packaging/windows/bobine-{channel}.ico", desktop, "ICO"))
    outputs.append(Output(f"packaging/macos/bobine-{channel}.icns", fit_on_square(master, ICNS_CANVAS, FULL_FILL), "ICNS"))

    # Android : calque avant adaptatif (compilé dans l'APK du canal) + bannière TV.
    for density, factor in ANDROID_DENSITIES.items():
        px = round(108 * factor)
        outputs.append(Output(
            f"android/app/src/channel-{channel}/res/mipmap-{density}/ic_launcher_foreground.png",
            fit_on_square(master, px, ADAPTIVE_FILL),
        ))
    outputs.append(Output(f"android/app/src/tv-channel-{channel}/res/drawable/banner_bobine_tv.png", tv_banner(master)))
    # Écran de démarrage : embarqué pour les trois canaux (suit le canal choisi à l'exécution).
    outputs.append(Output(
        f"android/app/src/main/res/drawable-nodpi/bobine_splash_logo_{channel}.png", resized(master, SPLASH_SIZE),
    ))

    # Application de bureau : icône de la barre système (suit le canal choisi à l'exécution).
    outputs.append(Output(f"Assets/Images/logo_bobine_icon_{channel}.png", resized(desktop, TRAY_SIZE)))

    # Interface web et assistant d'installation.
    outputs.append(Output(f"frontend/public/logo-{channel}.png", master))
    outputs.append(Output(f"frontend/public/favicon-{channel}.png", resized(desktop, FAVICON_SIZE)))
    outputs.append(Output(f"assistant/ui/assets/channel-{channel}.png", resized(master, ASSISTANT_SIZE)))

    # Visuels des README et des notes de version (dossier historique « Versions »).
    versions = resized(master, VERSIONS_SIZE)
    name = channel.capitalize()  # Stable, Beta, Canary (noms historiques des visuels de README)
    outputs.append(Output(f"Assets/Images/Versions/{name}.png", versions))
    outputs.append(Output(f"Assets/Images/Versions/{name}-cropped-1024.png", versions))

    if channel == DEFAULT_CHANNEL:
        # Icône « sans canal » historique (métadonnées AppStream, repli du tray) = Stable.
        outputs.append(Output("Assets/Images/logo_bobine_icon.png", resized(desktop, TRAY_SIZE)))
    return outputs


def all_outputs(channels: tuple[str, ...] = CHANNELS) -> list[Output]:
    result: list[Output] = []
    for channel in channels:
        result.extend(outputs_for_channel(channel))
    return result


def _save(output: Output, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if output.fmt == "ICO":
        output.image.save(destination, format="ICO", sizes=ICO_SIZES)
    elif output.fmt == "ICNS":
        output.image.save(destination, format="ICNS")
    else:
        output.image.save(destination, format="PNG", optimize=True)


def _largest_frame(path: Path) -> Image.Image:
    with Image.open(path) as image:
        if path.suffix == ".ico":
            biggest = max(image.info.get("sizes", {image.size}))
            image.size = biggest
        image.load()
        return image.convert("RGBA")


def _is_current(output: Output, destination: Path, tolerance: int = 3) -> bool:
    """Compare les pixels (tolérance d'arrondi entre versions de Pillow) plutôt que les octets."""
    if not destination.exists():
        return False
    try:
        on_disk = _largest_frame(destination)
    except Exception:
        return False
    expected = output.image.convert("RGBA")
    if output.fmt in ("ICO", "ICNS"):
        expected = expected.resize(on_disk.size, Image.Resampling.LANCZOS)
    if on_disk.size != expected.size:
        return False
    extrema = ImageChops.difference(on_disk, expected).getextrema()
    return max(high for _, high in extrema) <= tolerance


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="échoue si un fichier dérivé est absent ou périmé")
    parser.add_argument("--list", action="store_true", help="affiche les chemins produits, sans écrire")
    parser.add_argument("--channel", choices=CHANNELS, action="append", help="limite à un canal (répétable)")
    args = parser.parse_args(argv)

    outputs = all_outputs(tuple(args.channel) if args.channel else CHANNELS)

    if args.list:
        for output in outputs:
            print(output.path)
        return 0

    if args.check:
        stale = [o.path for o in outputs if not _is_current(o, REPO_DIR / o.path)]
        if stale:
            print(f"{len(stale)} fichier(s) absent(s) ou périmé(s) — relancer scripts/generate_channel_icons.py :", file=sys.stderr)
            for path in stale:
                print(f"  {path}", file=sys.stderr)
            return 1
        print(f"{len(outputs)} fichiers à jour.")
        return 0

    for output in outputs:
        _save(output, REPO_DIR / output.path)
    print(f"{len(outputs)} fichiers écrits ({', '.join(args.channel or CHANNELS)}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
