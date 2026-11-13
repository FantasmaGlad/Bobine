"""Analyseur d'arguments : options communes et arbre des commandes."""

from __future__ import annotations

import argparse

from app.api.contract import (
    CHANNELS,
    DASHBOARD_CHANNELS,
    DASHBOARD_PERIODS,
    DISPLAY_OUTPUTS,
    HISTORY_PERIODS,
    LOG_LEVELS,
    LOG_SOURCES,
    SCHEDULE_CHANNELS,
    SORT_ORDERS,
    VIDEO_SORT_FIELDS,
)

from .client import Client, local_version
from .completion import completion_script
from .config import cmd_backup, cmd_config, cmd_restore, cmd_settings
from .control import cmd_api, cmd_diagnose, cmd_open, cmd_playback, cmd_update, cmd_update_status
from .core import DEFAULT_TIMEOUT, EXIT_OK, Output
from .declared import add_import_commands, add_spec_commands
from .paging import paged
from .read import cmd_devices, cmd_display, cmd_imports, cmd_library, cmd_logs, cmd_metrics, cmd_playlists, cmd_schedule, cmd_status, cmd_storage


def _add_common_options(parser: argparse.ArgumentParser, *, suppress_defaults: bool = False) -> None:
    default = argparse.SUPPRESS if suppress_defaults else None
    parser.add_argument("--host", default=default, help="machine à piloter (défaut : 127.0.0.1, ou BOBINE_HOST)")
    parser.add_argument("--port", type=int, default=default, help="port de Bobine (défaut : port réel de la machine locale, ou BOBINE_PORT)")
    parser.add_argument("--timeout", type=float, default=default, metavar="SECONDES",
                        help=f"délai d'une requête (défaut : {DEFAULT_TIMEOUT:g} s, ou BOBINE_TIMEOUT)")
    parser.add_argument("--json", action="store_true", default=argparse.SUPPRESS if suppress_defaults else False,
                        help="réponse JSON brute sur stdout")
    parser.add_argument("-v", "--verbose", action="count", default=argparse.SUPPRESS if suppress_defaults else 0,
                        help="détail sur stderr (-vv : requêtes et réponses)")
    parser.add_argument("-q", "--quiet", action="store_true", default=argparse.SUPPRESS if suppress_defaults else False,
                        help="erreurs seulement")
    parser.add_argument("--no-color", action="store_true", default=argparse.SUPPRESS if suppress_defaults else False,
                        help="sans couleur (aussi : variable NO_COLOR)")


def _add_health(sub, common: argparse.ArgumentParser) -> None:
    sub.add_parser("status", parents=[common], help="santé et lecture en cours").set_defaults(run=cmd_status)
    diagnose = sub.add_parser("diagnose", parents=[common], help="diagnostic typé (code de sortie 1 si un problème est trouvé)")
    diagnose.add_argument("--auto-fix", action="store_true", help="corriger ce qui peut l'être sans risque (import bloqué, composant natif inutilisé)")
    diagnose.add_argument("--yes", action="store_true", help="avec --auto-fix : appliquer réellement")
    diagnose.set_defaults(run=cmd_diagnose)


def _add_catalog(sub, common: argparse.ArgumentParser) -> None:
    library = sub.add_parser("library", parents=[common], help="bibliothèque vidéo")
    library_sub = library.add_subparsers(dest="library_action", required=True)
    library_list = library_sub.add_parser("list", parents=[common], help="lister les vidéos")
    library_list.add_argument("--search")
    library_list.add_argument("--program")
    library_list.add_argument("--release")
    library_list.add_argument("--sort-by", dest="sort_by", choices=VIDEO_SORT_FIELDS, default="imported_at")
    library_list.add_argument("--order", choices=SORT_ORDERS, default="desc")
    paged(library_list)
    library_get = library_sub.add_parser("get", parents=[common], help="détail d'une vidéo")
    library_get.add_argument("video_id", type=int)
    library.set_defaults(run=cmd_library)
    playlists = sub.add_parser("playlists", parents=[common], help="playlists vidéo")
    playlists_sub = playlists.add_subparsers(dest="playlists_action", required=True)
    paged(playlists_sub.add_parser("list", parents=[common], help="lister les playlists"))
    playlists_get = playlists_sub.add_parser("get", parents=[common], help="détail d'une playlist")
    playlists_get.add_argument("playlist_id", type=int)
    playlists.set_defaults(run=cmd_playlists)
    schedule = sub.add_parser("schedule", parents=[common], help="planning de diffusion")
    schedule_sub = schedule.add_subparsers(dest="schedule_action", required=True)
    channels = SCHEDULE_CHANNELS
    schedule_list = schedule_sub.add_parser("list", parents=[common], help="lister les programmations")
    schedule_list.add_argument("--channel", choices=channels)
    paged(schedule_list)
    schedule_next = schedule_sub.add_parser("next", parents=[common], help="prochaine occurrence")
    schedule_next.add_argument("--channel", choices=channels)
    schedule_get = schedule_sub.add_parser("get", parents=[common], help="détail d'une programmation")
    schedule_get.add_argument("schedule_id", type=int)
    schedule.set_defaults(run=cmd_schedule)


def _add_machine(sub, common: argparse.ArgumentParser) -> None:
    devices = sub.add_parser("devices", parents=[common], help="périphériques de la machine")
    devices_sub = devices.add_subparsers(dest="devices_action", required=True)
    for name, help_text in (
        ("status", "état du pilote"), ("audio", "sorties audio"), ("bluetooth", "Bluetooth"),
        ("wifi", "Wi-Fi"), ("topology", "carte des périphériques"),
    ):
        devices_sub.add_parser(name, parents=[common], help=help_text)
    devices.set_defaults(run=cmd_devices)
    storage = sub.add_parser("storage", parents=[common], help="stockage externe")
    storage_sub = storage.add_subparsers(dest="storage_action", required=True)
    for name, help_text in (
        ("status", "état du service de stockage"), ("volumes", "supports amovibles"), ("portable", "téléphones"),
    ):
        storage_sub.add_parser(name, parents=[common], help=help_text)
    storage_browse = storage_sub.add_parser("browse", parents=[common], help="parcourir un support")
    storage_browse.add_argument("key")
    storage_browse.add_argument("--path", default="")
    storage_browse.add_argument("--limit", type=int, default=200)
    storage_browse.add_argument("--offset", type=int, default=0)
    storage_browse.add_argument("--show-hidden", dest="show_hidden", action="store_true", help="montrer les fichiers cachés")
    storage_browse.add_argument("--media-only", dest="media_only", action="store_true", help="ne montrer que les médias")
    storage.set_defaults(run=cmd_storage)
    metrics = sub.add_parser("metrics", parents=[common], help="métriques et télémétrie")
    metrics_sub = metrics.add_subparsers(dest="metrics_action", required=True)
    metrics_dashboard = metrics_sub.add_parser("dashboard", parents=[common], help="tableau de bord")
    metrics_dashboard.add_argument("--period", choices=DASHBOARD_PERIODS, default="30d")
    metrics_dashboard.add_argument("--channel", choices=DASHBOARD_CHANNELS, default="all")
    metrics_sub.add_parser("system", parents=[common], help="télémétrie matérielle courante")
    metrics_history = metrics_sub.add_parser("history", parents=[common], help="historique d'une métrique")
    metrics_history.add_argument("--metric", default="cpu")
    metrics_history.add_argument("--period", choices=HISTORY_PERIODS, default="1h")
    metrics.set_defaults(run=cmd_metrics)


def _add_activity(sub, common: argparse.ArgumentParser) -> None:
    imports = sub.add_parser("imports", parents=[common], help="file d'import et chaîne d'import")
    imports_sub = imports.add_subparsers(dest="imports_action", required=True)
    paged(imports_sub.add_parser("list", parents=[common], help="tâches d'import en cours et récentes"))
    imports_cancel = imports_sub.add_parser("cancel", parents=[common], help="annuler une tâche")
    imports_cancel.add_argument("job_id")
    imports_sub.add_parser("diagnose", parents=[common], help="diagnostic de la chaîne d'import")
    imports.set_defaults(run=cmd_imports)
    display = sub.add_parser("display", parents=[common], help="sortie affichée par canal")
    display_sub = display.add_subparsers(dest="display_action", required=True)
    display_sub.add_parser("get", parents=[common], help="lire les sorties câblé et réseau")
    display_set = display_sub.add_parser("set", parents=[common], help="basculer un canal")
    display_set.add_argument("channel", choices=CHANNELS)
    display_set.add_argument("output", choices=DISPLAY_OUTPUTS)
    display.set_defaults(run=cmd_display)


def _add_live(sub, common: argparse.ArgumentParser) -> None:
    logs = sub.add_parser("logs", parents=[common], help="journaux")
    logs.add_argument("--source", choices=LOG_SOURCES, default="technical")
    logs.add_argument("--level", choices=LOG_LEVELS)
    logs.add_argument("--since", help="date ISO 8601 avec fuseau, ex. 2026-11-05T08:00:00Z")
    logs.add_argument("--limit", type=int, default=200)
    logs.set_defaults(run=cmd_logs)

    for name, target, help_text in (("playback", "canal (cable, network)", "commande de lecture d'un canal"),
                                    ("radio", "sortie (cable, network)", "commande d'une sortie radio")):
        command = sub.add_parser(name, parents=[common], help=help_text,
                                 description="Mêmes actions que le WebSocket de l'interface ; paramètres en clé=valeur.")
        command.add_argument("target", metavar="cible", help=target)
        command.add_argument("action", help="ex. play, pause, stop, seek, volume, load")
        command.add_argument("params", nargs="*", metavar="clé=valeur")
        command.set_defaults(run=cmd_playback)


def _add_settings(sub, common: argparse.ArgumentParser) -> None:
    config = sub.add_parser("config", parents=[common], help="configuration en fichiers JSON")
    config_sub = config.add_subparsers(dest="config_action", required=True)
    export = config_sub.add_parser("export", parents=[common], help="exporter (un fichier par type de réglage)")
    export.add_argument("directory", nargs="?", help="dossier de destination (sinon stdout)")
    export.add_argument("--file", dest="name", help="un seul fichier, ex. schedule-cable.json")
    apply = config_sub.add_parser("apply", parents=[common], help="appliquer des fichiers (essai à blanc sans --yes)")
    apply.add_argument("paths", nargs="+", metavar="fichier-ou-dossier")
    apply.add_argument("--yes", action="store_true", help="appliquer réellement")
    apply.add_argument("--include-machine", action="store_true", help="appliquer aussi machine.json")
    config.set_defaults(run=cmd_config)

    settings = sub.add_parser("settings", parents=[common], help="lire ou modifier un réglage")
    settings_sub = settings.add_subparsers(dest="settings_action", required=True)
    get = settings_sub.add_parser("get", parents=[common])
    get.add_argument("key", nargs="?")
    put = settings_sub.add_parser("set", parents=[common])
    put.add_argument("pairs", nargs="+", metavar="clé=valeur")
    settings.set_defaults(run=cmd_settings)

    update = sub.add_parser("update", parents=[common], help="mises à jour")
    update_sub = update.add_subparsers(dest="update_action", required=True)
    update_sub.add_parser("check", parents=[common]).set_defaults(run=cmd_update)
    install = update_sub.add_parser("apply", parents=[common])
    install.add_argument("--yes", action="store_true", help="confirmer (Bobine redémarre)")
    install.set_defaults(run=cmd_update)
    update_sub.add_parser("status", parents=[common]).set_defaults(run=cmd_update_status)

    settings_backup = settings_sub.add_parser("backup", parents=[common], help="écrire une sauvegarde (zip) de la base et de la configuration")
    settings_backup.add_argument("file", help="fichier à créer (rien n'est écrasé)")
    settings_backup.set_defaults(run=cmd_backup)
    settings_restore = settings_sub.add_parser("restore", parents=[common], help="restaurer une sauvegarde (remplace la base, redémarre Bobine)")
    settings_restore.add_argument("file")
    settings_restore.add_argument("--yes", action="store_true", help="confirmer")
    settings_restore.set_defaults(run=cmd_restore)


def _add_raw(sub, common: argparse.ArgumentParser) -> None:
    api = sub.add_parser("api", parents=[common], help="appeler directement une route de l'API (ce qu'aucune commande ne couvre)")
    api.add_argument("method", choices=("GET", "POST", "PUT", "PATCH", "DELETE"))
    api.add_argument("path", help="chemin de la route, /api/...")
    api.add_argument("--query", action="append", metavar="clé=valeur", help="paramètre de requête (répétable)")
    api.add_argument("--body", help="corps JSON : texte, @fichier ou - (entrée standard)")
    api.add_argument("--yes", action="store_true", help="confirmer une écriture")
    api.set_defaults(run=cmd_api)


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    _add_common_options(common)
    sub_common = argparse.ArgumentParser(add_help=False)
    _add_common_options(sub_common, suppress_defaults=True)

    parser = argparse.ArgumentParser(
        prog="bobine", parents=[common], description="Piloter et diagnostiquer Bobine.",
        epilog="Sur l'appliance, bobine start, stop, restart et journal pilotent aussi ses services. "
               "Codes de sortie : 0 succès, 1 erreur ou problème trouvé, 2 usage, 3 injoignable, 4 refus.",
    )
    parser.add_argument("-V", "--version", action="version", version=f"bobine {local_version()}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="commande")

    _add_health(sub, sub_common)
    _add_catalog(sub, sub_common)
    _add_machine(sub, sub_common)
    _add_activity(sub, sub_common)
    _add_live(sub, sub_common)
    _add_settings(sub, sub_common)
    _add_raw(sub, sub_common)

    add_spec_commands(sub, sub_common)
    add_import_commands(sub, sub_common)

    completion = sub.add_parser("completion", parents=[sub_common], help="script de complétion pour bash, zsh ou fish")
    completion.add_argument("shell", choices=("bash", "zsh", "fish"))
    completion.set_defaults(run=cmd_completion)

    open_page = sub.add_parser("open", parents=[sub_common], help="ouvrir une page de Bobine dans le navigateur (port réel)")
    open_page.add_argument("page", nargs="?", default="admin", help="admin, grid, cinema, kiosk ou radio")
    open_page.set_defaults(run=cmd_open)

    sub.add_parser("version", parents=[sub_common], help="version de cette installation").set_defaults(
        run=lambda client, out, args: (out.result({"version": local_version()}, local_version()), EXIT_OK)[1])
    return parser


def cmd_completion(client: Client | None, out: Output, args: argparse.Namespace) -> int:
    print(completion_script(args.shell, build_parser()), end="")
    return EXIT_OK
