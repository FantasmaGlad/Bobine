"""Qui couvre quelle route de l'API : une commande `bobine`, ou une exemption motivée.

Chaque route de l'API (`/openapi.json`) est dans `COVERED` (commande qui l'appelle) ou décrite par une règle de `EXEMPT`.
`backend/tests/test_cli_contract.py` échoue quand une route ajoutée n'est dans aucune des deux : un nouveau bouton de
l'interface oblige donc à choisir, dans la même modification, entre une commande et une exemption.

Statut d'une exemption : `never` (pas de sens pour une commande, la raison le dit) ou `todo` (commande prévue : la
retirer d'ici et ajouter la route à `COVERED` quand elle existe). Les routes servent aussi `bobine api METHODE CHEMIN`
pour les cas non couverts, sauf celles de `app.cli.DANGEROUS_ROUTES`.
"""
from __future__ import annotations

import re
from typing import NamedTuple

# "METHODE chemin OpenAPI" -> commande `bobine` qui l'appelle.
from app.cli_commands import SPECS

COVERED: dict[str, str] = {
    "GET /api/health": "status",
    "GET /api/playback/state": "status",
    "POST /api/playback/{channel}/{action}": "playback",
    "GET /api/radio/state": "radio",
    "POST /api/radio/{output}/{action}": "radio",
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
    "GET /api/devices/wifi": "devices",
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
    "GET /api/settings/display-output": "display",
    "PUT /api/settings/display-output": "display",
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
    "POST /api/radio/tracks/upload": "radio-library",
    "POST /api/radio/tracks/upload-zip": "radio-library",
    "GET /api/settings/backup/export": "settings",
    "POST /api/settings/backup/restore": "settings",
}
# Les commandes déclarées dans app/cli_commands.py annoncent elles-mêmes leurs routes.
COVERED.update({route: spec.command for spec in SPECS for route in spec.covers})


class Exemption(NamedTuple):
    pattern: str  # expression régulière sur « METHODE chemin », en entier
    status: str  # "never" ou "todo"
    reason: str  # pourquoi, ou la commande prévue

    def matches(self, route: str) -> bool:
        return re.fullmatch(self.pattern, route) is not None


EXEMPT: tuple[Exemption, ...] = (
    # --- sans sens pour une commande -------------------------------------------------------------------------------------
    Exemption(r"GET /api/(videos/\{video_id\}|audio/tracks/\{track_id\}|backgrounds/\{background_id\}|radio/tracks/\{track_id\}|radio/announcements/\{announcement_id\})/stream",
              "never", "flux média pour un lecteur"),
    Exemption(r"GET /api/(radio/tracks/\{track_id\}/cover|videos/\{video_id\}/subtitles/\{subtitle_id\}/vtt)", "never", "contenu pour un lecteur ou un navigateur"),
    Exemption(r"GET /api/logs/technical/download", "never", "téléchargement du journal : `bobine logs` lit le même journal"),
    Exemption(r"POST /api/metrics/(sessions/(start|end)|ratings)", "never", "rapport émis par un lecteur"),
    Exemption(r"(GET|PUT) /api/display/state", "never", "rapport des clients natifs (écrans, Android)"),
    Exemption(r"POST /api/updates/(_android-callback|store/.+)", "never", "mise à jour par la boutique ou par Android"),
    Exemption(r"GET /api/time", "never", "horloge de synchronisation des lecteurs"),
    Exemption(r"POST /api/settings/open-path", "never", "ouvre un dossier sur l'écran de la machine"),
    Exemption(r"POST /api/settings/system/(reset|uninstall|reset-data)", "never", "irréversible : interface, ou install.sh --uninstall"),
    Exemption(r"POST /api/settings/system/restart", "never", "autre outil : bobine restart de l'appliance, menu de la barre système"),
    Exemption(r"GET /api/config", "never", "liste des fichiers : `bobine config export` les écrit"),
    # --- commandes prévues ---------------------------------------------------------------------------------------------
    Exemption(r"GET /api/metrics/ratings", "todo", "metrics ratings"),
    Exemption(r"(POST|GET|PATCH|DELETE) /api/uploads.*", "todo", "library import : protocole d'envoi par morceaux"),
    Exemption(r"(POST|PUT|DELETE) /api/videos(/.*)?", "todo", "library import|set|rm|subtitles|chapters"),
    Exemption(r"GET /api/videos/(programs|\{video_id\}/(subtitles|chapters(/export)?))", "todo", "library subtitles|chapters"),
    Exemption(r"(GET|POST|PUT|DELETE) /api/audio-playlists(/.*)?", "todo", "playlists --kind audio"),
    Exemption(r"(GET|POST|PUT|DELETE) /api/audio(/.*)?", "todo", "audio list|get|import|set|rm"),
    Exemption(r"(GET|POST|PUT|DELETE) /api/backgrounds(/.*)?", "todo", "backgrounds list|import|set|rm"),
    Exemption(r"GET /api/schedule/occurrences", "todo", "schedule occurrences"),
    Exemption(r"(GET|POST|PUT|PATCH|DELETE) /api/radio/(tracks|artists|albums|tags|playlists|announcements|announcement-rules|default-playlist|sound).*",
              "todo", "radio library|tags|playlists|announcements"),
    Exemption(r"(GET|PUT|DELETE|POST) /api/playback/interrupted.*", "todo", "playback resume|dismiss"),
    Exemption(r"(GET|POST|PUT|DELETE) /api/devices/.*", "todo", "devices audio|bluetooth|wifi|routing|mixer"),
    Exemption(r"(GET|POST|PUT|DELETE) /api/storage/.*", "todo", "storage volume|format"),
    Exemption(r"(GET|DELETE) /api/logs/(activity|technical).*", "todo", "logs purge|clear|types"),
    Exemption(r"(GET|POST|DELETE) /api/settings/(storage|logs/purge|media-native|logo|laptop-lid|backup/.*)", "todo", "settings backup|restore|logo|purge"),
    Exemption(r"POST /api/updates/(tor-check|acknowledge)", "todo", "update tor-check|acknowledge"),
)


def exemption_for(route: str) -> list[Exemption]:
    """Règles qui exemptent la route ; une route couverte par une commande n'est jamais exemptée (les règles par famille
    de `todo` peuvent donc rester larges)."""
    if route in COVERED:
        return []
    rules = [rule for rule in EXEMPT if rule.matches(route)]
    # Une règle « never » précise l'emporte sur la règle « todo » de sa famille (ex. le flux d'un morceau radio).
    return [rule for rule in rules if rule.status == "never"] or rules
