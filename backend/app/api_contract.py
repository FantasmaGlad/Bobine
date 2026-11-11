"""Valeurs que l'API, l'interface et la commande `bobine` doivent partager : canaux, sorties, périodes, niveaux, actions.

Module sans dépendance (ni FastAPI ni base) : les routeurs, les moteurs de lecture et `app.cli` l'importent, donc une
valeur ne se déclare qu'ici. `backend/tests/test_cli_contract.py` échoue si un routeur accepte autre chose que ce
module, ou si une route de l'API n'a ni commande `bobine` ni exemption motivée (`app/cli/routes.py`).
"""
from __future__ import annotations

# Canaux de diffusion vidéo ; chaque canal a son état de lecture, sa playlist, son kiosque primaire.
CHANNELS = ("cable", "network")
DEFAULT_CHANNEL = "cable"
# Sorties radio (une par canal) et ensemble des canaux d'un planning.
RADIO_CHANNELS = ("radio_cable", "radio_network")
LEGACY_RADIO_CHANNEL = "radio"
SCHEDULE_CHANNELS = CHANNELS + RADIO_CHANNELS
SCHEDULE_TARGETS = ("video", "playlist", "radio_playlist")
OVERRIDE_ACTIONS = ("cancelled", "replaced")

# Ce que chaque canal peut afficher ; la sortie radio n'existe que sur le canal câblé.
DISPLAY_OUTPUTS_BY_CHANNEL = {"cable": ("kiosk", "cinema", "radio"), "network": ("kiosk", "cinema")}
DISPLAY_OUTPUTS = ("kiosk", "cinema", "radio")

# Métriques : périodes du tableau de bord et de l'historique matériel.
DASHBOARD_PERIODS = ("7d", "30d", "this_month", "all")
HISTORY_PERIODS = ("1h", "6h", "24h", "7d", "30d", "this_month", "all")
DASHBOARD_CHANNELS = ("all",) + CHANNELS

# Bornes des réglages numériques de lecture : (minimum, maximum). Le serveur les refuse hors de ces bornes ; la page
# Réglages (frontend/src/lib/settingsBounds.ts, parité vérifiée par un test) les reprend pour ses champs.
SETTING_BOUNDS = {
    "wait_time_between_courses": (0, 3600),     # secondes d'attente entre deux cours d'une playlist
    "volume_default": (0, 100),                  # pourcentage
    "audio_chain_timer_seconds": (0, 86400),    # secondes entre deux pistes en mode minuterie
    "radio_announcement_fade_ms": (0, 10000),   # fondu d'un rappel radio, en millisecondes
}

# Journaux.
LOG_LEVELS = ("debug", "info", "warning", "error", "critical")
LOG_SOURCES = ("technical", "activity")

# Bibliothèque vidéo.
VIDEO_SORT_FIELDS = ("imported_at", "title", "duration")
SORT_ORDERS = ("asc", "desc")

# Actions de la façade REST de lecture : POST /api/playback/{canal}/{action} et POST /api/radio/{sortie}/{action}.
# Les rapports d'un écran (position, fins de média, niveaux) n'en font pas partie : l'écran primaire en a l'autorité.
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


def regex(values: tuple[str, ...]) -> str:
    """Motif de validation d'un paramètre de requête (`Query(pattern=...)`) qui n'accepte que ces valeurs."""
    return "^(" + "|".join(values) + ")$"
