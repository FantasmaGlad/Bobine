"""Décodage d'une image fixe par ffmpeg (ordinateurs) ; HEIC exige ffmpeg 7.1 ou plus récent."""
from __future__ import annotations

import re
import subprocess
from functools import lru_cache
from pathlib import Path

from app.utils.ffmpeg_binaries import FFMPEG_BIN, media_subprocess_kwargs, with_nostdin
from app.utils.video_utils.limits import FFMPEG_THUMBNAIL_TIMEOUT_SECONDS

HEIF = frozenset({".heic", ".heif"})


def supports_heif(version_line: str) -> bool:
    """Grilles HEIF lues depuis ffmpeg 7.1 ; une version de développement (N-…) est récente."""
    match = re.search(r"ffmpeg version (\S+)", version_line)
    if not match:
        return False
    version = match.group(1)
    if version.startswith(("N-", "git-")):
        return True
    numbers = re.match(r"n?(\d+)\.(\d+)", version)
    return bool(numbers) and (int(numbers.group(1)), int(numbers.group(2))) >= (7, 1)


@lru_cache(maxsize=1)
def _version_line() -> str:
    result = subprocess.run(with_nostdin([FFMPEG_BIN, "-hide_banner", "-version"]), capture_output=True, text=True,
                            timeout=FFMPEG_THUMBNAIL_TIMEOUT_SECONDS, **media_subprocess_kwargs())
    return (result.stdout or "").splitlines()[0] if result.stdout else ""


def decode(source: Path, dest: Path, extension: str) -> None:
    if extension in HEIF and not supports_heif(_version_line()):
        raise ValueError("les images HEIC demandent ffmpeg 7.1 ou plus récent sur cet ordinateur")
    cmd = [FFMPEG_BIN, "-hide_banner", "-loglevel", "error", "-y", "-i", str(source), "-frames:v", "1", "-c:v", "png", str(dest)]
    result = subprocess.run(with_nostdin(cmd), capture_output=True, text=True, timeout=FFMPEG_THUMBNAIL_TIMEOUT_SECONDS,
                            **media_subprocess_kwargs())
    if result.returncode != 0:
        raise ValueError(f"ffmpeg ne lit pas cette image : {(result.stderr or '').strip()[-300:]}")
