"""Planches d'aperçu des vidéos : génération par ffmpeg sur images clés, une vidéo à la fois en arrière-plan."""
from __future__ import annotations

import logging
import shutil
import subprocess
import threading
from pathlib import Path

from app.config import settings
from app.utils.executors import ffmpeg_executor
from app.utils.ffmpeg_binaries import FFMPEG_BIN, media_subprocess_kwargs, with_nostdin

from .storyboard_layout import StoryboardLayout, storyboard_layout

logger = logging.getLogger(__name__)

_pending = threading.Event()
_lock = threading.Lock()


def storyboard_dir(video_id: int) -> Path:
    return Path(settings.thumbnails_dir) / "storyboards" / str(video_id)


def sheet_path(video_id: int, sheet: int) -> Path:
    return storyboard_dir(video_id) / f"sheet-{sheet}.jpg"


def _command(source: str, folder: Path, layout: StoryboardLayout) -> list[str]:
    tile = f"scale={layout.tile_width}:{layout.tile_height}:force_original_aspect_ratio=decrease," \
           f"pad={layout.tile_width}:{layout.tile_height}:(ow-iw)/2:(oh-ih)/2"
    filters = f"fps=1/{layout.interval_seconds}:eof_action=pass,{tile},tile={layout.columns}x{layout.rows}"
    return [FFMPEG_BIN, "-hide_banner", "-loglevel", "error", "-y", "-skip_frame", "nokey", "-i", source,
            "-an", "-vf", filters, "-fps_mode", "vfr", "-q:v", "3", "-start_number", "0", str(folder / "sheet-%d.jpg")]


def _complete(folder: Path, layout: StoryboardLayout) -> bool:
    return all((folder / f"sheet-{n}.jpg").is_file() and (folder / f"sheet-{n}.jpg").stat().st_size > 0 for n in range(layout.sheets))


def generate_storyboard(video_id: int, source: str, duration_seconds: float | None) -> bool:
    layout = storyboard_layout(duration_seconds)
    if layout is None:
        return False
    dest = storyboard_dir(video_id)
    partial = dest.with_name(f"{video_id}.part")
    shutil.rmtree(partial, ignore_errors=True)
    partial.mkdir(parents=True)
    timeout = max(120, int(duration_seconds or 0) // 4)
    try:
        result = subprocess.run(with_nostdin(_command(source, partial, layout)), capture_output=True, text=True,
                                timeout=timeout, **media_subprocess_kwargs())
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.warning("Planches d'aperçu de la vidéo %s non générées : %s", video_id, exc)
        shutil.rmtree(partial, ignore_errors=True)
        return False
    if result.returncode != 0 or not _complete(partial, layout):
        logger.warning("Planches d'aperçu de la vidéo %s non générées : %s", video_id, (result.stderr or "").strip()[-300:])
        shutil.rmtree(partial, ignore_errors=True)
        return False
    shutil.rmtree(dest, ignore_errors=True)
    partial.rename(dest)
    return True


def remove_storyboard(video_id: int) -> None:
    shutil.rmtree(storyboard_dir(video_id), ignore_errors=True)


def is_stale(video_id: int, source: str) -> bool:
    first = sheet_path(video_id, 0)
    try:
        return not first.exists() or first.stat().st_mtime < Path(source).stat().st_mtime
    except OSError:
        return False


def _missing() -> list[tuple[int, str, float | None]]:
    from app.database import SessionLocal
    from app.models import Video

    with SessionLocal() as db:
        rows = db.query(Video.id, Video.file_path, Video.duration_seconds).filter(Video.storage_id.is_(None)).all()
    return [(vid, path, duration) for vid, path, duration in rows if duration and is_stale(vid, path)]


def _fill() -> None:
    while _pending.is_set():
        _pending.clear()
        with _lock:
            for video_id, source, duration in _missing():
                if generate_storyboard(video_id, source, duration):
                    logger.info("Planches d'aperçu de la vidéo %s générées", video_id)


def request_storyboards() -> None:
    """Demande la génération des mosaïques manquantes ; les demandes rapprochées n'en font qu'une."""
    if _pending.is_set():
        return
    _pending.set()
    ffmpeg_executor.submit(_fill)
