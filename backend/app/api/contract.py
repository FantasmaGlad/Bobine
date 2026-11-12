"""Valeurs que l'API, l'interface et la commande `bobine` doivent partager : canaux, sorties, périodes, niveaux, actions."""
from __future__ import annotations

DEFAULT_PORT = 1903
GITHUB_REPO = "FantasmaGlad/Bobine"

CHANNELS = ("cable", "network")
DEFAULT_CHANNEL = "cable"
RADIO_CHANNELS = ("radio_cable", "radio_network")
LEGACY_RADIO_CHANNEL = "radio"
SCHEDULE_CHANNELS = CHANNELS + RADIO_CHANNELS
SCHEDULE_TARGETS = ("video", "playlist", "radio_playlist")
OVERRIDE_ACTIONS = ("cancelled", "replaced")

DISPLAY_OUTPUTS_BY_CHANNEL = {"cable": ("kiosk", "cinema", "radio"), "network": ("kiosk", "cinema")}
DISPLAY_OUTPUTS = ("kiosk", "cinema", "radio")

DASHBOARD_PERIODS = ("7d", "30d", "this_month", "all")
HISTORY_PERIODS = ("1h", "6h", "24h", "7d", "30d", "this_month", "all")
DASHBOARD_CHANNELS = ("all",) + CHANNELS

SETTING_BOUNDS = {
    "wait_time_between_courses": (0, 3600),
    "volume_default": (0, 100),
    "audio_chain_timer_seconds": (0, 86400),
    "radio_announcement_fade_ms": (0, 10000),
}

LOG_LEVELS = ("debug", "info", "warning", "error", "critical")
LOG_SOURCES = ("technical", "activity")

VIDEO_SORT_FIELDS = ("imported_at", "title", "duration")
SORT_ORDERS = ("asc", "desc")

PLAYBACK_ACTIONS = (
    "load", "load_playlist", "load_background", "load_audio_course", "load_audio_playlist", "play", "pause", "stop",
    "seek", "speed", "volume", "set_sound", "set_subtitle", "next_video", "previous_video", "skip_waiting", "audio_set_background",
    "audio_next_track", "audio_previous_track", "audio_restart_track", "audio_jump_to_track", "audio_set_chain_mode",
    "audio_set_chain_timer", "cinema_command",
)
RADIO_ACTIONS = (
    "load_radio_playlist", "radio_shuffle_all", "play", "pause", "stop", "radio_next_track", "radio_previous_track",
    "radio_jump_to_track", "radio_seek", "volume", "radio_set_sound", "radio_meter", "radio_set_shuffle",
    "radio_set_repeat", "radio_add_to_queue", "radio_play_next", "radio_move_in_queue", "radio_remove_from_queue",
    "radio_play_announcement",
)
RADIO_OUTPUTS = {"cable": "radio_cable", "network": "radio_network"}
ANNOUNCEMENT_RULE_TYPES = ("every_n_tracks", "every_x_minutes", "fixed_times")
ANNOUNCEMENT_TARGETS = RADIO_CHANNELS + ("both",)
STORAGE_IMPORT_KINDS = ("video", "radio", "audio_course")
MOUNT_MODES = ("ro", "rw")
MEDIA_KINDS = ("video", "playlist", "audio", "audio-playlist", "background", "radio-track", "radio-playlist")
PLAYABLE_MEDIA = {
    "video": ("playback", "load", "video_id"),
    "playlist": ("playback", "load_playlist", "playlist_id"),
    "audio": ("playback", "load_audio_course", "audio_course_id"),
    "audio-playlist": ("playback", "load_audio_playlist", "audio_playlist_id"),
    "background": ("playback", "load_background", "background_id"),
    "radio-playlist": ("radio", "load_radio_playlist", "playlist_id"),
    "radio-track": ("radio", "radio_play_next", "track_id"),
}


def regex(values: tuple[str, ...]) -> str:
    """Motif de validation d'un paramètre de requête (`Query(pattern=...)`) qui n'accepte que ces valeurs."""
    return "^(" + "|".join(values) + ")$"
