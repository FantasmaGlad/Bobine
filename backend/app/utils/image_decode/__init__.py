"""Décodage des images que Pillow ne lit pas sur cette plateforme (AVIF, HEIC) vers un PNG lisible."""
from __future__ import annotations

from pathlib import Path

from .registry import platform_decoder


def decode_to_png(source: Path, original_filename: str) -> Path:
    """Décode `source` en PNG à côté de lui avec le décodeur de la plateforme ; lève ValueError si impossible."""
    dest = source.with_name(f"{source.name}.decoded.png")
    try:
        platform_decoder()(source, dest, Path(original_filename).suffix.lower())
    except ValueError:
        dest.unlink(missing_ok=True)
        raise
    except Exception as exc:
        dest.unlink(missing_ok=True)
        raise ValueError(f"décodage impossible sur cet appareil : {exc}") from exc
    if not dest.exists() or dest.stat().st_size == 0:
        dest.unlink(missing_ok=True)
        raise ValueError("le décodeur n'a produit aucune image")
    return dest
