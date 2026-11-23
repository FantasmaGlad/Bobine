"""Qui couvre quelle route de l'API : une commande `bobine`, ou une exemption motivée."""
from __future__ import annotations

import re
from typing import NamedTuple

from app.cli.specs import SPECS

COVERED: dict[str, str] = {
    "GET /api/health": "status",
    "GET /api/outputs": "output",
    "GET /api/outputs/{output_id}": "output",
    "PUT /api/outputs/{output_id}/mode": "output",
    "POST /api/outputs/{output_id}/playback/{action}": "output",
    "POST /api/outputs/{output_id}/radio/{action}": "output",
    "GET /api/videos": "library",
    "GET /api/videos/{video_id}": "library",
    "GET /api/playlists": "playlists",
    "GET /api/playlists/{playlist_id}": "playlists",
    "GET /api/schedule": "schedule",
    "GET /api/schedule/next": "schedule",
    "GET /api/schedule/{schedule_id}": "schedule",
    "GET /api/devices/status": "devices",
    "GET /api/devices/audio": "devices",
    "GET /api/devices/bluetooth": "devices",
    "GET /api/devices/topology": "devices",
    "GET /api/storage/status": "storage",
    "GET /api/storage/volumes": "storage",
    "GET /api/storage/portable": "storage",
    "GET /api/storage/volumes/{key}/browse": "storage",
    "GET /api/metrics/dashboard": "metrics",
    "GET /api/metrics/hardware/history": "metrics",
    "GET /api/settings/system": "metrics",
    "GET /api/import-jobs": "imports",
    "DELETE /api/import-jobs/{job_id}": "imports",
    "GET /api/diagnostics/import": "imports",
    "GET /api/diagnostics/system": "diagnose",
    "GET /api/logs": "logs",
    "GET /api/config/export": "config",
    "GET /api/config/export/{name}": "config",
    "POST /api/config/apply": "config",
    "GET /api/settings": "settings",
    "PUT /api/settings": "settings",
    "GET /api/updates/check": "update",
    "GET /api/updates/status": "update",
    "POST /api/updates/apply": "update",
    "POST /api/videos/upload": "library",
    "POST /api/audio/upload": "audio",
    "POST /api/audio/upload-zip": "audio",
    "POST /api/backgrounds/upload": "backgrounds",
    "POST /api/backgrounds/upload-zip": "backgrounds",
    "POST /api/visuals/upload": "visuals",
    "POST /api/visuals/upload-zip": "visuals",
    "POST /api/videos/upload-zip": "library",
    "POST /api/radio/tracks/upload": "radio-library",
    "POST /api/radio/tracks/upload-zip": "radio-library",
    "GET /api/settings/backup/export": "settings",
    "POST /api/settings/backup/restore": "settings",
    "GET /api/media": "media",
}
COVERED.update({route: spec.command for spec in SPECS for route in spec.covers})


class Exemption(NamedTuple):
    pattern: str
    reason: str

    def matches(self, route: str) -> bool:
        return re.fullmatch(self.pattern, route) is not None


EXEMPT: tuple[Exemption, ...] = (
    Exemption(r"GET /api/(videos/\{video_id\}|audio/tracks/\{track_id\}|backgrounds/\{background_id\}|visuals/\{visual_id\}|radio/tracks/\{track_id\}|radio/announcements/\{announcement_id\})/stream", "flux média pour un lecteur"),
    Exemption(r"GET /api/(radio/tracks/\{track_id\}/cover|videos/\{video_id\}/subtitles/\{subtitle_id\}/vtt)", "contenu pour un lecteur ou un navigateur"),
    Exemption(r"GET /api/logs/technical/download", "téléchargement du journal : `bobine logs` lit le même journal"),
    Exemption(r"POST /api/metrics/(sessions/(start|end)|ratings)", "rapport émis par un lecteur"),
    Exemption(r"(GET|PUT) /api/display/state", "rapport des clients natifs (écrans, Android)"),
    Exemption(r"POST /api/updates/(_android-callback|store/.+)", "mise à jour par la boutique ou par Android"),
    Exemption(r"GET /api/time", "horloge de synchronisation des lecteurs"),
    Exemption(r"POST /api/settings/open-path", "ouvre un dossier sur l'écran de la machine"),
    Exemption(r"POST /api/settings/system/(reset|uninstall|reset-data)", "irréversible : depuis l'interface seulement"),
    Exemption(r"POST /api/settings/system/restart", "autre outil : menu de la barre système"),
    Exemption(r"GET /api/config", "liste des fichiers : `bobine config export` les écrit"),
    Exemption(r"(POST|GET|PATCH|DELETE) /api/uploads.*", "envoi reprenable par morceaux du navigateur : `bobine <famille> import` envoie en une fois"),
)


def exemption_for(route: str) -> list[Exemption]:
    """Règles qui exemptent la route ; une route couverte par une commande n'est jamais exemptée."""
    if route in COVERED:
        return []
    return [rule for rule in EXEMPT if rule.matches(route)]
