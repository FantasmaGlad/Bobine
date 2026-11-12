"""Native inspection for new audio imports only (opt-in, with strict fallback)."""
from __future__ import annotations

import io
import logging
import os
from pathlib import Path
import tempfile

from app.utils import audio_utils, media_native, radio_utils
from app.utils.media_sidecar import get_media_client

logger = logging.getLogger(__name__)

COVER_MAX_SIZE = (600, 600)
COVER_JPEG_QUALITY = 85


def _probe(file_path: str, profile: str) -> dict | None:
    if not media_native.is_enabled():
        return None
    return get_media_client().probe_audio(file_path, profile)


def extract_radio_metadata(file_path: str) -> dict:
    """Use verified native tags, preserving the historical filename fallback."""
    metadata = _probe(file_path, "radio-v1")
    if metadata is None:
        return radio_utils.extract_radio_metadata(file_path)
    result = dict(metadata)
    if not result["title"]:
        result["title"] = radio_utils.clean_filename_label(file_path)
    return result


def extract_audio_duration(file_path: str) -> float | None:
    """Course imports consume only duration; filenames and ordering stay in Python."""
    metadata = _probe(file_path, "course-duration-v1")
    if metadata is None:
        return audio_utils.extract_audio_duration(file_path)
    return metadata["duration_seconds"]


def render_cover(data: bytes) -> bytes:
    """The Pillow step of the cover pipeline, from the raw bytes of an embedded picture."""
    from PIL import Image

    with Image.open(io.BytesIO(data)) as image:
        image = image.convert("RGB")
        image.thumbnail(COVER_MAX_SIZE)
        output = io.BytesIO()
        image.save(output, "JPEG", quality=COVER_JPEG_QUALITY)
    return output.getvalue()


def _write_native_cover(data: bytes, covers_dir: str, file_id: str) -> str | None:
    try:
        rendered = render_cover(data)
        folder = Path(covers_dir)
        folder.mkdir(parents=True, exist_ok=True)
        destination = folder / f"cover_{file_id}.jpg"
        handle = tempfile.NamedTemporaryFile(dir=folder, suffix=".tmp", delete=False)
        try:
            with handle:
                handle.write(rendered)
            os.replace(handle.name, destination)
        except BaseException:
            try:
                os.remove(handle.name)
            except OSError:
                pass
            raise
        return str(destination)
    except Exception as exc:
        logger.info("Native cover not usable (%s): reference pipeline", type(exc).__name__)
        return None


def extract_embedded_cover(file_path: str, covers_dir: str, file_id: str) -> str | None:
    """Native cover when the component proves absence or hands over an eligible picture."""
    if media_native.is_enabled():
        cover = get_media_client().extract_cover(file_path)
        if cover.available:
            if cover.data is None:
                return None
            written = _write_native_cover(cover.data, covers_dir, file_id)
            if written is not None:
                return written
    return radio_utils.extract_embedded_cover(file_path, covers_dir, file_id)
