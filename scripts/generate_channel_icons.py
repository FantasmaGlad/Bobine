#!/usr/bin/env python3
"""Génère toutes les icônes dérivées des icônes de canal (Stable, Bêta, Canary)."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops

REPO_DIR = Path(__file__).resolve().parent.parent
SOURCE_DIR = REPO_DIR / "Assets" / "Images" / "channel-icons"

_spec = importlib.util.spec_from_file_location("bobine_release_channel", REPO_DIR / "backend" / "app" / "release_channel.py")
_registry = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _registry
_spec.loader.exec_module(_registry)
CHANNELS = _registry.CHANNEL_IDS
DEFAULT_CHANNEL = _registry.DEFAULT_CHANNEL

FULL_FILL = 0.90
ADAPTIVE_FILL = 0.572

LINUX_SIZES = (16, 24, 32, 48, 64, 128, 256, 512)
LINUX_PIXMAP_SIZE = 256
ICO_SIZES = [(s, s) for s in (16, 24, 32, 48, 64, 128, 256)]
ICNS_CANVAS = 1024
TRAY_SIZE = 256
FAVICON_SIZE = 64
VERSIONS_SIZE = 1024
SPLASH_SIZE = 512

ANDROID_DENSITIES = {"mdpi": 1.0, "hdpi": 1.5, "xhdpi": 2.0, "xxhdpi": 3.0, "xxxhdpi": 4.0}

BANNER_SIZE = (640, 360)
BANNER_ICON_BOX = (54, 87, 156, 186)
BANNER_WORDMARK_ORIGIN = (212, 132)


@dataclass(frozen=True)
class Output:
    """Un fichier produit : chemin relatif au dépôt, image, format."""

    path: str
    image: Image.Image
    fmt: str = "PNG"


def master_path(channel: str) -> Path:
    return SOURCE_DIR / f"bobine-channel-{channel}.png"


def load_master(channel: str, size: int = 512) -> Image.Image:
    path = master_path(channel)
    if not path.exists():
        raise FileNotFoundError(f"Icône source absente : {path.relative_to(REPO_DIR)}")
    image = Image.open(path).convert("RGBA")
    if image.size != (size, size):
        raise ValueError(f"{path.name} doit mesurer {size} x {size} (trouvé {image.size[0]} x {image.size[1]})")
    return image


def fit_on_square(source: Image.Image, size: int, fill: float) -> Image.Image:
    """Recadre le dessin sur sa boîte englobante, le met à l'échelle sans déformation (plus grande dimension = `fill` x `size`) et le centre sur un carré transparent."""
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

    linux_root = f"packaging/linux/icons/{channel}"
    for size in LINUX_SIZES:
        outputs.append(Output(f"{linux_root}/hicolor/{size}x{size}/apps/com.bobine.app.png", resized(desktop, size)))
    outputs.append(Output(f"{linux_root}/pixmaps/com.bobine.app.png", resized(desktop, LINUX_PIXMAP_SIZE)))

    outputs.append(Output(f"packaging/windows/bobine-{channel}.ico", desktop, "ICO"))
    outputs.append(Output(f"packaging/macos/bobine-{channel}.icns", fit_on_square(master, ICNS_CANVAS, FULL_FILL), "ICNS"))

    for density, factor in ANDROID_DENSITIES.items():
        px = round(108 * factor)
        outputs.append(Output(
            f"android/app/src/channel-{channel}/res/mipmap-{density}/ic_launcher_foreground.png",
            fit_on_square(master, px, ADAPTIVE_FILL),
        ))
    outputs.append(Output(f"android/app/src/tv-channel-{channel}/res/drawable/banner_bobine_tv.png", tv_banner(master)))
    outputs.append(Output(
        f"android/app/src/main/res/drawable-nodpi/bobine_splash_logo_{channel}.png", resized(master, SPLASH_SIZE),
    ))

    outputs.append(Output(f"Assets/Images/logo_bobine_icon_{channel}.png", resized(desktop, TRAY_SIZE)))

    outputs.append(Output(f"frontend/public/logo-{channel}.png", master))
    outputs.append(Output(f"frontend/public/favicon-{channel}.png", resized(desktop, FAVICON_SIZE)))

    versions = resized(master, VERSIONS_SIZE)
    name = channel.capitalize()
    outputs.append(Output(f"Assets/Images/Versions/{name}.png", versions))
    outputs.append(Output(f"Assets/Images/Versions/{name}-cropped-1024.png", versions))

    if channel == DEFAULT_CHANNEL:
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
