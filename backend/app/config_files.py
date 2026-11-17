"""Configuration de Bobine en fichiers JSON lisibles, rangés par famille : schéma, noms et sérialisation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.api.contract import SCHEDULE_CHANNELS

SCHEMA = 2


ACCEPTED_SCHEMAS = (1, 2)


def schedule_path(channel: str) -> str:
    return f"schedule/{channel.replace('_', '-')}.json"


KINDS: dict[str, str] = {
    "manifest.json": "manifest",
    "settings.json": "settings",
    "machine.json": "machine",
    "outputs/display.json": "display-outputs",
    "outputs/radio.json": "radio-outputs",
    "library/videos.json": "library-videos",
    "library/audio.json": "library-audio",
    "library/radio.json": "library-radio",
    "library/backgrounds.json": "library-backgrounds",
    "library/announcements.json": "announcements",
    "playlists/video.json": "playlists-video",
    "playlists/audio.json": "playlists-audio",
    "playlists/radio.json": "playlists-radio",
    **{schedule_path(c): f"schedule-{c.replace('_', '-')}" for c in SCHEDULE_CHANNELS},
    "radio/tags.json": "radio-tags",
    "radio/announcement-rules.json": "announcement-rules",
}


LEGACY_NAMES: dict[str, str] = {
    "display-outputs.json": "outputs/display.json",
    "radio-outputs.json": "outputs/radio.json",
    "announcements.json": "library/announcements.json",
    "playlists-video.json": "playlists/video.json",
    "playlists-audio.json": "playlists/audio.json",
    "playlists-radio.json": "playlists/radio.json",
    **{f"schedule-{c.replace('_', '-')}.json": schedule_path(c) for c in SCHEDULE_CHANNELS},
    "radio-tags.json": "radio/tags.json",
    "announcement-rules.json": "radio/announcement-rules.json",
}


def canonical_name(name: str) -> str:
    """Nom d'un fichier dans l'arborescence actuelle (traduit les noms plats de la version 5.1)."""
    return LEGACY_NAMES.get(name.replace("\\", "/"), name.replace("\\", "/"))


PORTABLE_SETTINGS = (
    "theme", "theme_mode", "language", "active_logo", "update_channel", "auto_update_enabled", "auto_update_time",
    "wait_time_between_courses", "volume_default", "audio_chain_timer_seconds", "logs_retention_days",
    "radio_announcement_fade_ms", "auto_web_rendition", "simplified_ui",
)


def dumps(document: dict[str, Any]) -> str:
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"


def file_name(path: str | None) -> str | None:
    return Path(path).name if path else None


def envelope(kind: str, body: dict[str, Any], warnings: list[str] | None = None) -> dict[str, Any]:
    document: dict[str, Any] = {"schema": SCHEMA, "kind": kind, **body}
    if warnings:
        document["warnings"] = warnings
    return document
