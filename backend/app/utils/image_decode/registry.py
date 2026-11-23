"""Choix du décodeur d'images selon le profil de déploiement."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from app.utils.deployment import get_deployment_profile

Decoder = Callable[[Path, Path, str], None]


def platform_decoder(profile: str | None = None) -> Decoder:
    if (profile or get_deployment_profile()) == "android":
        from .android import decode

        return decode
    from .ffmpeg_still import decode

    return decode
