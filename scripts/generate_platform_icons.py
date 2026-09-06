#!/usr/bin/env python3
"""Générateur d'icônes multi-plateformes pour Bobine.

Prend l'icône source `Assets/Images/logo_bobine_icon.png` (non carrée), la cadre
parfaitement sur un canevas carré transparent 1024x1024 sans déformation de ratio
d'aspect, et produit les icônes nécessaires à toutes les plateformes de distribution :
  - Windows : `packaging/windows/bobine.ico` (multi-résolution : 16, 24, 32, 48, 64, 128, 256)
  - macOS   : `packaging/macos/bobine.icns` (multi-résolution Apple iconset Retina)
  - Linux   : `packaging/linux/icons/hicolor/{16..512}x{16..512}/apps/bobine.png`
              et `packaging/linux/icons/pixmaps/bobine.png`
"""

import os
from pathlib import Path
from PIL import Image

REPO_DIR = Path(__file__).resolve().parent.parent
SRC_PATH = REPO_DIR / "Assets" / "Images" / "logo_bobine_icon.png"


def create_master_square(src_img: Image.Image, size: int = 1024, padding_ratio: float = 0.90) -> Image.Image:
    """Cadre l'image source sur un canevas carré avec marges confortables,
    en préservant strictement les proportions d'origine."""
    rgba = src_img.convert("RGBA")
    bbox = rgba.getbbox()
    if bbox:
        cropped = rgba.crop(bbox)
    else:
        cropped = rgba

    cw, ch = cropped.size
    target_max = int(size * padding_ratio)
    scale = target_max / max(cw, ch)
    nw, nh = int(cw * scale), int(ch * scale)

    resized = cropped.resize((nw, nh), Image.Resampling.LANCZOS)
    master = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    paste_x = (size - nw) // 2
    paste_y = (size - nh) // 2
    master.paste(resized, (paste_x, paste_y))
    return master


def generate_icons() -> None:
    if not SRC_PATH.exists():
        raise FileNotFoundError(f"Source icon not found at {SRC_PATH}")

    src_img = Image.open(SRC_PATH)
    master = create_master_square(src_img, size=1024, padding_ratio=0.90)

    # 1. Windows ICO
    ico_path = REPO_DIR / "packaging" / "windows" / "bobine.ico"
    ico_path.parent.mkdir(parents=True, exist_ok=True)
    ico_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    master.save(str(ico_path), format="ICO", sizes=ico_sizes)
    print(f"[Windows] Généré {ico_path} ({os.path.getsize(ico_path)} octets, tailles={ico_sizes})")

    # 2. macOS ICNS
    icns_path = REPO_DIR / "packaging" / "macos" / "bobine.icns"
    icns_path.parent.mkdir(parents=True, exist_ok=True)
    master.save(str(icns_path), format="ICNS")
    print(f"[macOS]   Généré {icns_path} ({os.path.getsize(icns_path)} octets)")

    # 3. Linux PNGs
    linux_sizes = [16, 24, 32, 48, 64, 128, 256, 512]
    for s in linux_sizes:
        hicolor_dir = REPO_DIR / "packaging" / "linux" / "icons" / "hicolor" / f"{s}x{s}" / "apps"
        hicolor_dir.mkdir(parents=True, exist_ok=True)
        out_img = master.resize((s, s), Image.Resampling.LANCZOS)
        out_path = hicolor_dir / "bobine.png"
        out_img.save(str(out_path), format="PNG")

    pixmaps_dir = REPO_DIR / "packaging" / "linux" / "icons" / "pixmaps"
    pixmaps_dir.mkdir(parents=True, exist_ok=True)
    pixmap_path = pixmaps_dir / "bobine.png"
    master.resize((256, 256), Image.Resampling.LANCZOS).save(str(pixmap_path), format="PNG")
    print(f"[Linux]   Généré {len(linux_sizes)} icônes hicolor + pixmaps dans packaging/linux/icons/")


if __name__ == "__main__":
    generate_icons()
