"""Experimental native inspection for new audio imports only.

The opt-in leaves reference utilities unchanged, including database backfills.
The client validates the native contract and requests fallback on transport or
format errors. Embedded images retain the reference normalization pipeline until
image parity is established; only a proven absence skips that pipeline.
"""
from __future__ import annotations

import os

from app.utils import audio_utils, radio_utils
from app.utils.media_sidecar import get_media_client


def _probe(file_path: str, profile: str) -> dict | None:
    # Avoid even creating the singleton on installations that have not opted in.
    if os.environ.get("BOBINE_MEDIA_NATIVE") != "1":
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


def extract_embedded_cover(file_path: str, covers_dir: str, file_id: str) -> str | None:
    """Skip image extraction only when the native reader proves there is no image."""
    if os.environ.get("BOBINE_MEDIA_NATIVE") == "1":
        cover = get_media_client().extract_cover(file_path)
        if cover.available and cover.data is None:
            return None
    # Future raw image support is not image parity: preserve ffmpeg + Pillow.
    return radio_utils.extract_embedded_cover(file_path, covers_dir, file_id)
