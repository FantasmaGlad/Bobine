"""Icône du plateau : couleur du canal de mise à jour courant."""


from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

from PIL import Image

from app.desktop import channel_icon

from .tray_urls import _admin_url


def _fetch_settings() -> dict | None:
    request = urllib.request.Request(f"{_admin_url()}/api/settings", headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=1.0) as response:
        return json.loads(response.read().decode())


def _detect_current_channel() -> str:
    return channel_icon.detect_channel(_fetch_settings)


def _load_icon_image(channel: str | None = None) -> Image.Image:
    if channel is None:
        channel = _detect_current_channel()
    exe_dir = Path(sys.executable).resolve().parent
    images_dir = Path(__file__).resolve().parent.parent.parent.parent / "Assets" / "Images"
    return channel_icon.load_tray_image(channel, channel_icon.icon_candidates(channel, exe_dir, images_dir))
