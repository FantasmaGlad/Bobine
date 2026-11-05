"""Commande `bobine` : piloter et diagnostiquer Bobine sans navigateur, en local ou sur une machine du réseau.

Client HTTP de l'API (mêmes routes que l'interface, aucune logique propre), bibliothèque standard seulement : la
commande démarre vite et marche aussi sur l'appliance. Sortie minimale par défaut, `-v` et `-vv` pour le détail sur
stderr, `--json` pour la réponse brute sur stdout. Codes de sortie : 0 succès, 1 erreur ou problème trouvé, 2 usage,
3 Bobine injoignable, 4 refus (canal verrouillé, élément introuvable...).
"""
from __future__ import annotations

import argparse
import http.client
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

EXIT_OK, EXIT_ERROR, EXIT_USAGE, EXIT_UNREACHABLE, EXIT_REFUSED = 0, 1, 2, 3, 4
COMMANDS = ("status", "diagnose", "logs", "playback", "radio", "config", "settings", "update", "version")
_REFUSAL_STATUSES = {404, 409, 503}


class CliError(Exception):
    def __init__(self, message: str, code: int = EXIT_ERROR, payload: Any = None) -> None:
        super().__init__(message)
        self.code, self.payload = code, payload


class Output:
    def __init__(self, args: argparse.Namespace) -> None:
        self.json = args.json
        self.verbosity = -1 if args.quiet else args.verbose
        self.color = sys.stdout.isatty() and not args.no_color and "NO_COLOR" not in os.environ

    def log(self, level: int, message: str) -> None:
        if self.verbosity >= level:
            print(message, file=sys.stderr)

    def paint(self, text: str, color: str) -> str:
        codes = {"red": "31", "yellow": "33", "green": "32", "dim": "2"}
        return f"\033[{codes[color]}m{text}\033[0m" if self.color else text

    def result(self, payload: Any, human: str | None = None) -> None:
        if self.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        elif human and self.verbosity >= 0:
            print(human)


class Client:
    def __init__(self, host: str, port: int, out: Output, timeout: float = 30.0) -> None:
        self.base = f"http://{host}:{port}"
        self.out, self.timeout = out, timeout

    def request(
        self, method: str, path: str, *, query: dict | None = None, body: Any = None,
        accept_status: frozenset[int] = frozenset(),
    ) -> Any:
        url = self.base + path + (f"?{urllib.parse.urlencode({k: v for k, v in query.items() if v is not None})}" if query else "")
        data = json.dumps(body).encode("utf-8") if body is not None else None
        self.out.log(1, f"{method} {url}")
        if data is not None:
            self.out.log(2, f"> {data.decode('utf-8')}")
        started = time.monotonic()
        try:
            req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"} if data else {})
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
                status = resp.status
        except urllib.error.HTTPError as exc:
            raw, status = exc.read(), exc.code
        except (urllib.error.URLError, OSError, http.client.HTTPException, ValueError) as exc:
            raise CliError(f"Bobine injoignable sur {self.base} ({getattr(exc, 'reason', exc)}).", EXIT_UNREACHABLE) from exc
        self.out.log(2, f"< {status} en {1000 * (time.monotonic() - started):.0f} ms : {raw[:2000].decode('utf-8', 'replace')}")
        try:
            payload = json.loads(raw) if raw else None
        except ValueError:
            payload = raw.decode("utf-8", "replace")
        if status >= 400 and status not in accept_status:
            detail = payload.get("detail") if isinstance(payload, dict) else payload
            if isinstance(detail, dict):
                message = detail.get("message") or detail.get("code") or f"réponse {status}"
            elif isinstance(detail, list):
                message = " ; ".join(str(item.get("msg", item)) if isinstance(item, dict) else str(item) for item in detail)
            else:
                message = str(detail) if detail else f"réponse {status}"
            if isinstance(detail, dict) and detail.get("allowed"):
                message += " Admis : " + ", ".join(map(str, detail["allowed"]))
            errors = detail.get("errors") if isinstance(detail, dict) else None
            if errors:
                message = message + "\n" + "\n".join(f"  - {e}" for e in errors)
            code = EXIT_REFUSED if status in _REFUSAL_STATUSES else EXIT_USAGE if status in (400, 422) else EXIT_ERROR
            raise CliError(f"Refusé ({status}) : {message}", code, payload)
        if not isinstance(payload, dict):
            raise CliError(f"réponse non JSON ({status}) de {url} : {raw[:200]!r}", EXIT_ERROR, payload)
        return payload


# --- paramètres « clé=valeur » des commandes de lecture ------------------------------------------------------------

def parse_params(pairs: list[str]) -> dict[str, Any]:
    """`video_id=12 volume=40 subtitle=off` : la valeur est lue en JSON quand c'est possible, sinon en texte."""
    params: dict[str, Any] = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep or not key:
            raise CliError(f"paramètre invalide : {pair!r} (attendu clé=valeur)", EXIT_USAGE)
        try:
            params[key] = json.loads(value)
        except ValueError:
            params[key] = value
    return params


# --- commandes ---------------------------------------------------------------------------------------------------------

def cmd_status(client: Client, out: Output, args: argparse.Namespace) -> int:
    health = client.request("GET", "/api/health", accept_status={503})
    playback = {channel: client.request("GET", "/api/playback/state", query={"channel": channel}) for channel in ("cable", "network")}
    payload = {"health": health, "playback": playback}
    lines = [f"Bobine sur {client.base} : {health.get('status')}"]
    for channel, data in playback.items():
        current = (data.get("current_video") or data.get("current_audio_course") or data.get("current_background") or {}).get("title") or "-"
        lines.append(f"  {channel} : {data.get('state')}, {current}")
    out.result(payload, "\n".join(lines))
    return EXIT_OK if health.get("status") == "ok" else EXIT_ERROR


def cmd_diagnose(client: Client, out: Output, args: argparse.Namespace) -> int:
    report = client.request("GET", "/api/diagnostics/system")
    colors = {"critical": "red", "warning": "yellow", "info": "dim"}
    lines = [f"État : {report['status']}"]
    for problem in report["problems"]:
        lines.append(f"  {out.paint(problem['severity'], colors[problem['severity']])} {problem['code']} : {problem['message']}")
        lines.append(f"    remède : {problem['remedy']}")
    if out.verbosity >= 1:
        lines += [f"  sonde {c['name']} : {c['status']}" + (f" ({c['detail']})" if c.get("detail") else "") for c in report["checks"]]
    out.result(report, "\n".join(lines))
    return EXIT_OK if report["status"] == "ok" else EXIT_ERROR


def cmd_logs(client: Client, out: Output, args: argparse.Namespace) -> int:
    payload = client.request("GET", "/api/logs", query={"source": args.source, "level": args.level, "since": args.since, "limit": args.limit})
    lines = [f"{e['timestamp']} {e['level'].upper():8} {e['category']}: {e['message']}" for e in reversed(payload["entries"])]
    if payload.get("truncated"):
        lines.insert(0, out.paint(f"(plus ancien tronqué : --limit {args.limit})", "dim"))
    out.result(payload, "\n".join(lines))
    return EXIT_OK


def cmd_playback(client: Client, out: Output, args: argparse.Namespace) -> int:
    prefix = "/api/playback" if args.command == "playback" else "/api/radio"
    payload = client.request("POST", f"{prefix}/{args.target}/{args.action}", body=parse_params(args.params))
    state = payload.get("state") or {}
    out.result(payload, f"{args.target} : {state.get('state', 'ok')}")
    return EXIT_OK


def _read_documents(paths: list[str]) -> dict[str, Any]:
    files: dict[str, Any] = {}
    for raw in paths:
        path = Path(raw)
        targets = sorted(path.glob("*.json")) if path.is_dir() else [path]
        for target in targets:
            try:
                files[target.name] = json.loads(target.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise CliError(f"{target} illisible : {exc}", EXIT_USAGE) from exc
    if not files:
        raise CliError("aucun fichier JSON à appliquer", EXIT_USAGE)
    return files


def cmd_config(client: Client, out: Output, args: argparse.Namespace) -> int:
    if args.config_action == "export":
        exported = client.request("GET", "/api/config/export")["files"]
        if args.name:
            exported = {args.name: exported[args.name]} if args.name in exported else None
            if exported is None:
                raise CliError(f"fichier inconnu : {args.name}", EXIT_USAGE)
        if args.directory:
            target = Path(args.directory)
            try:
                target.mkdir(parents=True, exist_ok=True)
                for name, document in exported.items():
                    (target / name).write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            except OSError as exc:
                raise CliError(f"écriture impossible dans {target} : {exc}", EXIT_ERROR) from exc
            out.result({"written": sorted(exported), "directory": str(target)}, f"{len(exported)} fichier(s) écrit(s) dans {target}")
        else:
            out.json = True  # sans dossier, le document part sur stdout pour une redirection
            out.result(exported if not args.name else exported[args.name])
        return EXIT_OK
    files = _read_documents(args.paths)
    result = client.request("POST", "/api/config/apply", query={
        "dry_run": "false" if args.yes else "true", "include_machine": "true" if args.include_machine else "false",
    }, body={"files": files})
    lines = []
    for name, diff in result["changes"].items():
        lines.append(out.paint(f"{name} :", "yellow"))
        lines += [f"  {line}" for line in diff if line[:1] in "+-" and not line.startswith(("+++", "---"))]
    if not result["changes"]:
        lines.append("Aucun écart.")
    lines += [f"ignoré (sans --include-machine) : {name}" for name in result["skipped"]]
    if result["restart_required"]:
        lines.append("redémarrage requis pour : " + ", ".join(result["restart_required"]))
    lines.append("Appliqué." if result["applied"] else "Essai à blanc : rien n'a été écrit (--yes pour appliquer).")
    out.result(result, "\n".join(lines))
    return EXIT_OK


def cmd_settings(client: Client, out: Output, args: argparse.Namespace) -> int:
    if args.settings_action == "get":
        settings = client.request("GET", "/api/settings")
        if args.key and args.key not in settings:
            raise CliError(f"réglage inconnu : {args.key}", EXIT_ERROR)
        value = settings if not args.key else settings[args.key]
        out.result(value, json.dumps(value, ensure_ascii=False, indent=2) if not isinstance(value, str) else value)
        return EXIT_OK
    changes = parse_params(args.pairs)
    # Les réglages booléens se stockent en texte « true » ou « false » côté serveur.
    body = {k: ("true" if v else "false") if isinstance(v, bool) else v for k, v in changes.items()}
    client.request("PUT", "/api/settings", body=body)
    out.result(body, "Réglage(s) enregistré(s) : " + ", ".join(body))
    return EXIT_OK


def cmd_update(client: Client, out: Output, args: argparse.Namespace) -> int:
    if args.update_action == "check":
        info = client.request("GET", "/api/updates/check", query={"refresh": 1})
        human = (f"Mise à jour disponible : {info.get('latest_version')}" if info.get("has_update")
                 else f"À jour ({info.get('current_version')})")
        out.result(info, human)
        return EXIT_OK
    if not args.yes:
        raise CliError("la mise à jour redémarre Bobine : ajouter --yes pour confirmer", EXIT_USAGE)
    out.result(client.request("POST", "/api/updates/apply"), "Mise à jour lancée (suivi : bobine update status).")
    return EXIT_OK


def cmd_update_status(client: Client, out: Output, args: argparse.Namespace) -> int:
    status = client.request("GET", "/api/updates/status")
    out.result(status, f"{status.get('step')} {status.get('percent') or ''} {status.get('message') or ''}".strip())
    return EXIT_OK


def local_version() -> str:
    try:
        from app.utils.version import get_app_version

        return get_app_version()
    except Exception:  # noqa: BLE001 — la version ne doit jamais empêcher la commande de répondre
        return "inconnue"


# --- analyse des arguments -------------------------------------------------------------------------------------------

def _default_port() -> int:
    """Port à joindre quand `--port` n'est pas fourni : `BOBINE_PORT`, sinon le port réel de la machine locale."""
    raw = os.environ.get("BOBINE_PORT")
    if raw:
        try:
            port = int(raw)
        except ValueError as exc:
            raise CliError(f"BOBINE_PORT invalide : {raw!r} (entier attendu).", EXIT_USAGE) from exc
        if not 1 <= port <= 65535:
            raise CliError(f"BOBINE_PORT hors bornes : {port} (1 à 65535).", EXIT_USAGE)
        return port
    try:
        from app.utils.port import current_port

        return current_port()
    except Exception:  # noqa: BLE001 — sans fichier d'exécution lisible, le port par défaut de Bobine
        return 1903


def _add_common_options(parser: argparse.ArgumentParser, *, suppress_defaults: bool = False) -> None:
    """Ajoute les options communes, acceptées avant comme après la sous-commande.

    Un sous-analyseur hérite de ces options par `parents`, mais argparse les ré-analyse dans un espace de noms neuf
    et ré-applique leurs valeurs par défaut : une option globale lue avant la sous-commande serait alors écrasée.
    Avec `suppress_defaults`, une option absente ne pose aucune valeur et celle déjà lue est conservée.
    """
    default = argparse.SUPPRESS if suppress_defaults else None
    parser.add_argument("--host", default=default, help="machine à piloter (défaut : 127.0.0.1, ou BOBINE_HOST)")
    parser.add_argument("--port", type=int, default=default, help="port de Bobine (défaut : port réel de la machine locale, ou BOBINE_PORT)")
    parser.add_argument("--json", action="store_true", default=argparse.SUPPRESS if suppress_defaults else False,
                        help="réponse JSON brute sur stdout")
    parser.add_argument("-v", "--verbose", action="count", default=argparse.SUPPRESS if suppress_defaults else 0,
                        help="détail sur stderr (-vv : requêtes et réponses)")
    parser.add_argument("-q", "--quiet", action="store_true", default=argparse.SUPPRESS if suppress_defaults else False,
                        help="erreurs seulement")
    parser.add_argument("--no-color", action="store_true", default=argparse.SUPPRESS if suppress_defaults else False,
                        help="sans couleur (aussi : variable NO_COLOR)")


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
    parser.add_argument("--version", action="version", version=f"bobine {local_version()}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="commande")

    sub.add_parser("status", parents=[sub_common], help="santé et lecture en cours").set_defaults(run=cmd_status)
    sub.add_parser("diagnose", parents=[sub_common], help="diagnostic typé (code de sortie 1 si un problème est trouvé)").set_defaults(run=cmd_diagnose)

    logs = sub.add_parser("logs", parents=[sub_common], help="journaux")
    logs.add_argument("--source", choices=("technical", "activity"), default="technical")
    logs.add_argument("--level", choices=("debug", "info", "warning", "error", "critical"))
    logs.add_argument("--since", help="date ISO 8601 avec fuseau, ex. 2026-11-05T08:00:00Z")
    logs.add_argument("--limit", type=int, default=200)
    logs.set_defaults(run=cmd_logs)

    for name, target, help_text in (("playback", "canal (cable, network)", "commande de lecture d'un canal"),
                                    ("radio", "sortie (cable, network)", "commande d'une sortie radio")):
        command = sub.add_parser(name, parents=[sub_common], help=help_text,
                                 description="Mêmes actions que le WebSocket de l'interface ; paramètres en clé=valeur.")
        command.add_argument("target", metavar="cible", help=target)
        command.add_argument("action", help="ex. play, pause, stop, seek, volume, load")
        command.add_argument("params", nargs="*", metavar="clé=valeur")
        command.set_defaults(run=cmd_playback)

    config = sub.add_parser("config", parents=[sub_common], help="configuration en fichiers JSON")
    config_sub = config.add_subparsers(dest="config_action", required=True)
    export = config_sub.add_parser("export", parents=[sub_common], help="exporter (un fichier par type de réglage)")
    export.add_argument("directory", nargs="?", help="dossier de destination (sinon stdout)")
    export.add_argument("--file", dest="name", help="un seul fichier, ex. schedule-cable.json")
    apply = config_sub.add_parser("apply", parents=[sub_common], help="appliquer des fichiers (essai à blanc sans --yes)")
    apply.add_argument("paths", nargs="+", metavar="fichier-ou-dossier")
    apply.add_argument("--yes", action="store_true", help="appliquer réellement")
    apply.add_argument("--include-machine", action="store_true", help="appliquer aussi machine.json")
    config.set_defaults(run=cmd_config)

    settings = sub.add_parser("settings", parents=[sub_common], help="lire ou modifier un réglage")
    settings_sub = settings.add_subparsers(dest="settings_action", required=True)
    get = settings_sub.add_parser("get", parents=[sub_common])
    get.add_argument("key", nargs="?")
    put = settings_sub.add_parser("set", parents=[sub_common])
    put.add_argument("pairs", nargs="+", metavar="clé=valeur")
    settings.set_defaults(run=cmd_settings)

    update = sub.add_parser("update", parents=[sub_common], help="mises à jour")
    update_sub = update.add_subparsers(dest="update_action", required=True)
    update_sub.add_parser("check", parents=[sub_common]).set_defaults(run=cmd_update)
    install = update_sub.add_parser("apply", parents=[sub_common])
    install.add_argument("--yes", action="store_true", help="confirmer (Bobine redémarre)")
    install.set_defaults(run=cmd_update)
    update_sub.add_parser("status", parents=[sub_common]).set_defaults(run=cmd_update_status)

    sub.add_parser("version", parents=[sub_common], help="version de cette installation").set_defaults(
        run=lambda client, out, args: (out.result({"version": local_version()}, local_version()), EXIT_OK)[1])
    return parser


def _prepare_windows_output() -> None:
    """Sous Windows, une sortie redirigée utilise la page de code ANSI (cp1252 en français) : un titre ou un journal
    non latin ferait échouer `print`. Le remplacement par des échappements Unicode garde un JSON valide et évite la
    traceback ; la console, elle, reste en Unicode."""
    if sys.platform != "win32":
        return
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="backslashreplace")
        except (AttributeError, OSError, ValueError):
            pass


def main(argv: list[str] | None = None) -> int:
    _prepare_windows_output()
    parser = build_parser()
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        parser.print_help()
        return EXIT_USAGE
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # argparse : 0 pour --help et --version, 2 pour une erreur d'usage
        return int(exc.code or 0)
    out = Output(args)
    try:
        host = args.host or os.environ.get("BOBINE_HOST", "127.0.0.1")
        port = args.port if args.port is not None else _default_port()
        if not 1 <= port <= 65535:
            raise CliError(f"port invalide : {port} (1 à 65535).", EXIT_USAGE)
        client = Client(host, port, out)
        return args.run(client, out, args)
    except CliError as exc:
        if out.json and exc.payload is not None:
            print(json.dumps(exc.payload, ensure_ascii=False, indent=2))
        print(f"bobine : {exc}", file=sys.stderr)
        return exc.code
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
