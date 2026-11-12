"""Applicateur de chaque fichier et ordre d'application."""
from __future__ import annotations
from typing import Callable
from app import config_files
from app.config_apply.apply_library import _apply_library_audio, _apply_library_backgrounds, _apply_library_radio, _apply_library_videos
from app.config_apply.apply_playlists import _apply_audio_playlists, _apply_video_playlists
from app.config_apply.apply_radio import _apply_announcement_rules, _apply_announcements, _apply_radio_outputs, _apply_radio_playlists, _apply_radio_tags
from app.config_apply.apply_schedule import _apply_schedule
from app.config_apply.apply_settings import _apply_display_outputs, _apply_machine, _apply_settings
from app.config_apply.context import _Context


APPLIERS: dict[str, Callable[[_Context, str, dict], None]] = {
    "settings.json": _apply_settings,
    "outputs/display.json": _apply_display_outputs,
    "outputs/radio.json": _apply_radio_outputs,
    "library/videos.json": _apply_library_videos,
    "library/audio.json": _apply_library_audio,
    "library/radio.json": _apply_library_radio,
    "library/backgrounds.json": _apply_library_backgrounds,
    "library/announcements.json": _apply_announcements,
    "playlists/video.json": _apply_video_playlists,
    "playlists/audio.json": _apply_audio_playlists,
    "playlists/radio.json": _apply_radio_playlists,
    "radio/tags.json": _apply_radio_tags,
    "radio/announcement-rules.json": _apply_announcement_rules,
    **{config_files.schedule_path(c): (lambda ctx, f, d, c=c: _apply_schedule(ctx, f, d, c))
       for c in config_files.SCHEDULE_CHANNELS},
    "machine.json": _apply_machine,
}


# Ordre d'application : les métadonnées des médias et les playlists avant ce qui les cite. `outputs/radio.json` vient
# après `playlists/radio.json` : son ambiance par défaut se désigne par un nom ou un `uid`, qui doit déjà exister (ou
# venir d'être créé dans la même transaction).
ORDER = [
    "settings.json",
    "outputs/display.json",
    "library/videos.json",
    "library/audio.json",
    "library/radio.json",
    "library/backgrounds.json",
    "library/announcements.json",
    "playlists/video.json",
    "playlists/audio.json",
    "playlists/radio.json",
    "outputs/radio.json",
    "radio/tags.json",
    "radio/announcement-rules.json",
    *[config_files.schedule_path(channel) for channel in config_files.SCHEDULE_CHANNELS],
    "machine.json",
]
