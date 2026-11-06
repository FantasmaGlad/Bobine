"""Commande `bobine` : piloter et diagnostiquer Bobine sans navigateur, en local ou sur une machine du réseau.

Client HTTP de l'API (mêmes routes que l'interface, aucune logique propre), bibliothèque standard seulement : la
commande démarre vite et marche aussi sur l'appliance. Sortie minimale par défaut, `-v` et `-vv` pour le détail sur
stderr, `--json` pour la réponse de l'API sur stdout (`status`, qui fait deux requêtes, rend `health` et `playback`). Codes
de sortie : 0 succès, 1 erreur ou problème trouvé, 2 usage (400, 422), 3 Bobine injoignable, 4 refus (403, 404, 409, 503 :
canal verrouillé, élément introuvable...).
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
COMMANDS = ("status", "diagnose", "library", "playlists", "schedule", "devices", "storage", "metrics", "imports", "display", "logs", "playback", "radio", "config", "settings", "update", "version")
_REFUSAL_STATUSES = {403, 404, 409, 503}
DEFAULT_TIMEOUT = 30.0


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


def segment(value: object) -> str:
    """Un identifiant inséré dans un chemin d'URL : jamais de `/`, `?`, `#` ou `..` pris pour de la structure."""
    return urllib.parse.quote(str(value), safe="")


class Client:
    def __init__(self, host: str, port: int, out: Output, timeout: float = DEFAULT_TIMEOUT) -> None:
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
        if payload is not None and not isinstance(payload, (dict, list)):
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


def cmd_library(client: Client, out: Output, args: argparse.Namespace) -> int:
    if args.library_action == "list":
        videos = client.request("GET", "/api/videos", query={
            "search": args.search, "program": args.program, "sort_by": args.sort_by, "order": args.order,
        })
        lines = []
        for video in videos:
            duration = video.get("duration_seconds")
            suffix = f" ({duration / 60:.0f} min)" if duration else ""
            lines.append(f"{video.get('id')}  {video.get('title')}{suffix}")
        out.result(videos, "\n".join(lines))
        return EXIT_OK
    video = client.request("GET", f"/api/videos/{segment(args.video_id)}")
    out.result(video, f"{video.get('id')}  {video.get('title')}")
    return EXIT_OK


def cmd_playlists(client: Client, out: Output, args: argparse.Namespace) -> int:
    if args.playlists_action == "list":
        playlists = client.request("GET", "/api/playlists")
        lines = [f"{p.get('id')}  {p.get('name')} ({p.get('item_count', 0)} élément(s))" for p in playlists]
        out.result(playlists, "\n".join(lines))
        return EXIT_OK
    playlist = client.request("GET", f"/api/playlists/{segment(args.playlist_id)}")
    lines = [f"{playlist.get('id')}  {playlist.get('name')}"]
    for item in playlist.get("items", []):
        video = item.get("video") or {}
        lines.append(f"  {video.get('id')}  {video.get('title')}")
    out.result(playlist, "\n".join(lines))
    return EXIT_OK


def cmd_schedule(client: Client, out: Output, args: argparse.Namespace) -> int:
    if args.schedule_action == "list":
        schedules = client.request("GET", "/api/schedule", query={"channel": args.channel})
        lines = []
        for schedule in schedules:
            when = schedule.get("time_of_day") or schedule.get("run_at") or "?"
            if schedule.get("days_of_week") and schedule.get("time_of_day"):
                names = ("lun", "mar", "mer", "jeu", "ven", "sam", "dim")
                when = ",".join(names[d] for d in schedule["days_of_week"] if isinstance(d, int) and 0 <= d < 7) + " " + when
            state = "actif" if schedule.get("active") else "inactif"
            lines.append(
                f"#{schedule.get('id')}  {schedule.get('channel')}  {when}  "
                f"{schedule.get('target_title') or schedule.get('target_type')}  {state}"
            )
        out.result(schedules, "\n".join(lines))
        return EXIT_OK
    if args.schedule_action == "next":
        upcoming = client.request("GET", "/api/schedule/next", query={"channel": args.channel})
        if upcoming is None:
            out.result(None, "Aucune occurrence à venir.")
        else:
            out.result(upcoming, f"{upcoming.get('run_at')}  {upcoming.get('title')}")
        return EXIT_OK
    schedule = client.request("GET", f"/api/schedule/{segment(args.schedule_id)}")
    lines = [
        f"#{schedule.get('id')}  {schedule.get('channel')}  {schedule.get('target_title') or schedule.get('target_type')}",
        f"  type={schedule.get('schedule_type')} actif={schedule.get('active')} "
        f"jours={schedule.get('days_of_week')} heure={schedule.get('time_of_day')} début={schedule.get('run_at')}",
    ]
    out.result(schedule, "\n".join(lines))
    return EXIT_OK


def cmd_devices(client: Client, out: Output, args: argparse.Namespace) -> int:
    action = args.devices_action
    payload = client.request("GET", f"/api/devices/{segment(action)}")
    if action == "status":
        lines = [
            f"{payload.get('platform')} / {payload.get('driver')}  "
            f"local={'oui' if payload.get('local') else 'non'}"
        ]
    elif action == "audio":
        if not payload.get("supported"):
            lines = [payload.get("reason") or "Sorties audio non disponibles."]
        else:
            devices = payload.get("devices", [])
            lines = [f"{len(devices)} sortie(s) audio, défaut : {payload.get('default_id') or '-'}"]
            lines += [f"  {d.get('id')}  {d.get('name')}{' (défaut)' if d.get('is_default') else ''}" for d in devices]
    elif action == "bluetooth":
        if not payload.get("supported"):
            lines = [payload.get("reason") or "Bluetooth non disponible."]
        else:
            devices = payload.get("devices", [])
            lines = [f"powered={payload.get('powered')} discovering={payload.get('discovering')} ({len(devices)} appareil(s))"]
            lines += [f"  {d.get('address')}  {d.get('name')}{' connecté' if d.get('connected') else ''}" for d in devices]
    elif action == "wifi":
        if not payload.get("supported"):
            lines = [payload.get("reason") or "Wi-Fi non disponible."]
        else:
            current = payload.get("current") or {}
            lines = [f"enabled={payload.get('enabled')}  ssid={current.get('ssid') or '-'}  ip={current.get('ip') or '-'}"]
            lines += [f"  {n.get('ssid')}  {n.get('signal')}%" for n in payload.get("networks", [])]
    else:
        counts = payload.get("counts") or {}
        lines = [
            f"{len(payload.get('nodes', []))} nœud(s), {len(payload.get('links', []))} lien(s)  "
            f"audio={counts.get('audio', 0)} bluetooth={counts.get('bluetooth', 0)} écrans={counts.get('screens', 0)}"
        ]
    out.result(payload, "\n".join(lines))
    return EXIT_OK


def cmd_storage(client: Client, out: Output, args: argparse.Namespace) -> int:
    action = args.storage_action
    if action == "browse":
        key = urllib.parse.quote(args.key, safe="")
        payload = client.request("GET", f"/api/storage/volumes/{segment(key)}/browse", query={
            "path": args.path, "limit": args.limit,
        })
        lines = [f"{payload.get('path') or '/'} ({payload.get('total', 0)} élément(s))"]
        lines += [
            f"  {entry.get('type')}  {entry.get('path') or entry.get('name')}  {entry.get('size') or '-'}"
            for entry in payload.get("entries", [])
        ]
        out.result(payload, "\n".join(lines))
        return EXIT_OK
    payload = client.request("GET", f"/api/storage/{segment(action)}")
    if action == "status":
        lines = [
            f"{payload.get('driver')}  prêt={payload.get('ready')}  "
            f"libre={payload.get('free_local_bytes')} o"
        ]
    elif action == "volumes":
        volumes = payload.get("volumes", [])
        lines = [f"{len(volumes)} support(s)"]
        lines += [f"  {v.get('key')}  {v.get('name')}  {v.get('state')}" for v in volumes]
    else:
        devices = payload.get("devices", [])
        lines = [f"{len(devices)} appareil(s) portable(s)"]
        lines += [f"  {d.get('id')}  {d.get('name')}  {d.get('state')}" for d in devices]
    out.result(payload, "\n".join(lines))
    return EXIT_OK


def cmd_metrics(client: Client, out: Output, args: argparse.Namespace) -> int:
    if args.metrics_action == "dashboard":
        payload = client.request("GET", "/api/metrics/dashboard", query={
            "period": args.period, "channel": args.channel,
        })
        kpis = payload.get("kpis") or {}
        completion = kpis.get("completion") or {}
        broadcast = kpis.get("broadcast") or {}
        sessions = kpis.get("sessions") or {}
        lines = [
            f"période={payload.get('period')} canal={payload.get('channel')}",
            f"  sessions={sessions.get('total', 0)} terminées={completion.get('completed_sessions', 0)} "
            f"({completion.get('rate', 0)} %) diffusé={broadcast.get('total_hours', 0)} h",
        ]
    elif args.metrics_action == "system":
        payload = client.request("GET", "/api/settings/system")
        lines = [
            f"CPU {payload.get('cpu_percent')} % ({payload.get('cpu_temp_c')} °C)  "
            f"RAM {payload.get('memory_percent')} %  GPU {payload.get('gpu_percent')} %  "
            f"puissance {payload.get('power_watts')} W",
        ]
    else:
        payload = client.request("GET", "/api/metrics/hardware/history", query={
            "metric": args.metric, "period": args.period,
        })
        lines = [
            f"{payload.get('label')} : {payload.get('current')} {payload.get('unit')}  "
            f"min={payload.get('min')} max={payload.get('max')} moyenne={payload.get('avg')} "
            f"({payload.get('count', 0)} point(s))",
        ]
    out.result(payload, "\n".join(lines))
    return EXIT_OK


def cmd_imports(client: Client, out: Output, args: argparse.Namespace) -> int:
    if args.imports_action == "list":
        jobs = client.request("GET", "/api/import-jobs")
        lines = [
            f"{job.get('id')}  {job.get('stage')}  {job.get('filename')}  {job.get('progress_percent') or 0} %"
            for job in jobs
        ]
        out.result(jobs, "\n".join(lines))
        return EXIT_OK
    if args.imports_action == "cancel":
        payload = client.request("DELETE", f"/api/import-jobs/{segment(args.job_id)}")
        out.result(payload, f"Tâche {args.job_id} annulée.")
        return EXIT_OK
    report = client.request("GET", "/api/diagnostics/import")
    problems = report.get("problems") or []
    lines = [f"constat : {problem}" for problem in problems] or ["Aucun problème détecté."]
    out.result(report, "\n".join(lines))
    return EXIT_ERROR if problems else EXIT_OK


def cmd_display(client: Client, out: Output, args: argparse.Namespace) -> int:
    if args.display_action == "get":
        payload = client.request("GET", "/api/settings/display-output")
    else:
        if args.channel == "network" and args.output == "radio":
            raise CliError("la sortie radio n'est disponible que sur le canal câblé", EXIT_USAGE)
        payload = client.request("PUT", "/api/settings/display-output", body={
            "channel": args.channel, "output": args.output,
        })
    out.result(payload, f"câblé={payload.get('cable')}  réseau={payload.get('network')}")
    return EXIT_OK


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
    channel = args.target if args.command == "playback" else f"radio_{args.target}"
    if args.action == "status":
        payload = client.request("GET", f"{prefix}/state", query={"channel": channel})
        state = payload.get("state") or payload.get("playing")
        out.result(payload, f"{args.target} : {state if state is not None else 'inconnu'}")
        return EXIT_OK
    payload = client.request("POST", f"{prefix}/{segment(args.target)}/{segment(args.action)}", body=parse_params(args.params))
    state = payload.get("state") or {}
    out.result(payload, f"{args.target} : {state.get('state', 'ok')}")
    return EXIT_OK


def _read_documents(paths: list[str]) -> dict[str, Any]:
    files: dict[str, Any] = {}
    for raw in paths:
        path = Path(raw)
        targets = sorted(path.glob("*.json")) if path.is_dir() else [path]
        for target in targets:
            if target.name in files:
                raise CliError(f"deux fichiers nommés {target.name} : l'un écraserait l'autre (le nom désigne le type de réglage).", EXIT_USAGE)
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
            raise CliError(f"réglage inconnu : {args.key}", EXIT_USAGE)
        value = settings if not args.key else settings[args.key]
        out.result(value, json.dumps(value, ensure_ascii=False, indent=2) if not isinstance(value, str) else value)
        return EXIT_OK
    changes = parse_params(args.pairs)
    # Les réglages booléens se stockent en texte « true » ou « false » côté serveur.
    body = {k: ("true" if v else "false") if isinstance(v, bool) else v for k, v in changes.items()}
    saved = client.request("PUT", "/api/settings", body=body)
    message = "Réglage(s) enregistré(s) : " + ", ".join(body)
    if isinstance(saved, dict) and saved.get("language_restart_required"):
        message += "\nLa langue s'applique au redémarrage de Bobine."
    out.result(saved if saved is not None else body, message)
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

def _timeout(args: argparse.Namespace) -> float:
    raw = args.timeout if args.timeout is not None else os.environ.get("BOBINE_TIMEOUT")
    try:
        value = float(raw) if raw not in (None, "") else DEFAULT_TIMEOUT
    except ValueError:
        raise CliError(f"délai invalide : {raw!r} (secondes, par exemple 10).", EXIT_USAGE) from None
    if not 0 < value <= 3600:
        raise CliError(f"délai invalide : {value:g} (entre 0 et 3600 secondes).", EXIT_USAGE)
    return value


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

    library = sub.add_parser("library", parents=[sub_common], help="bibliothèque vidéo")
    library_sub = library.add_subparsers(dest="library_action", required=True)
    library_list = library_sub.add_parser("list", parents=[sub_common], help="lister les vidéos")
    library_list.add_argument("--search")
    library_list.add_argument("--program")
    library_list.add_argument("--sort-by", dest="sort_by", choices=("imported_at", "title", "duration"), default="imported_at")
    library_list.add_argument("--order", choices=("asc", "desc"), default="desc")
    library_get = library_sub.add_parser("get", parents=[sub_common], help="détail d'une vidéo")
    library_get.add_argument("video_id", type=int)
    library.set_defaults(run=cmd_library)
    playlists = sub.add_parser("playlists", parents=[sub_common], help="playlists vidéo")
    playlists_sub = playlists.add_subparsers(dest="playlists_action", required=True)
    playlists_sub.add_parser("list", parents=[sub_common], help="lister les playlists")
    playlists_get = playlists_sub.add_parser("get", parents=[sub_common], help="détail d'une playlist")
    playlists_get.add_argument("playlist_id", type=int)
    playlists.set_defaults(run=cmd_playlists)
    schedule = sub.add_parser("schedule", parents=[sub_common], help="planning de diffusion")
    schedule_sub = schedule.add_subparsers(dest="schedule_action", required=True)
    channels = ("cable", "network", "radio_cable", "radio_network")
    schedule_list = schedule_sub.add_parser("list", parents=[sub_common], help="lister les programmations")
    schedule_list.add_argument("--channel", choices=channels)
    schedule_next = schedule_sub.add_parser("next", parents=[sub_common], help="prochaine occurrence")
    schedule_next.add_argument("--channel", choices=channels)
    schedule_get = schedule_sub.add_parser("get", parents=[sub_common], help="détail d'une programmation")
    schedule_get.add_argument("schedule_id", type=int)
    schedule.set_defaults(run=cmd_schedule)
    devices = sub.add_parser("devices", parents=[sub_common], help="périphériques de la machine")
    devices_sub = devices.add_subparsers(dest="devices_action", required=True)
    for name, help_text in (
        ("status", "état du pilote"), ("audio", "sorties audio"), ("bluetooth", "Bluetooth"),
        ("wifi", "Wi-Fi"), ("topology", "carte des périphériques"),
    ):
        devices_sub.add_parser(name, parents=[sub_common], help=help_text)
    devices.set_defaults(run=cmd_devices)
    storage = sub.add_parser("storage", parents=[sub_common], help="stockage externe")
    storage_sub = storage.add_subparsers(dest="storage_action", required=True)
    for name, help_text in (
        ("status", "état du service de stockage"), ("volumes", "supports amovibles"), ("portable", "téléphones"),
    ):
        storage_sub.add_parser(name, parents=[sub_common], help=help_text)
    storage_browse = storage_sub.add_parser("browse", parents=[sub_common], help="parcourir un support")
    storage_browse.add_argument("key")
    storage_browse.add_argument("--path", default="")
    storage_browse.add_argument("--limit", type=int, default=200)
    storage.set_defaults(run=cmd_storage)
    metrics = sub.add_parser("metrics", parents=[sub_common], help="métriques et télémétrie")
    metrics_sub = metrics.add_subparsers(dest="metrics_action", required=True)
    metrics_dashboard = metrics_sub.add_parser("dashboard", parents=[sub_common], help="tableau de bord")
    metrics_dashboard.add_argument("--period", choices=("7d", "30d", "this_month", "all"), default="30d")
    metrics_dashboard.add_argument("--channel", choices=("all", "cable", "network"), default="all")
    metrics_sub.add_parser("system", parents=[sub_common], help="télémétrie matérielle courante")
    metrics_history = metrics_sub.add_parser("history", parents=[sub_common], help="historique d'une métrique")
    metrics_history.add_argument("--metric", default="cpu")
    metrics_history.add_argument("--period", choices=("1h", "6h", "24h", "7d", "30d", "this_month", "all"), default="1h")
    metrics.set_defaults(run=cmd_metrics)
    imports = sub.add_parser("imports", parents=[sub_common], help="file d'import et chaîne d'import")
    imports_sub = imports.add_subparsers(dest="imports_action", required=True)
    imports_sub.add_parser("list", parents=[sub_common], help="tâches d'import en cours et récentes")
    imports_cancel = imports_sub.add_parser("cancel", parents=[sub_common], help="annuler une tâche")
    imports_cancel.add_argument("job_id")
    imports_sub.add_parser("diagnose", parents=[sub_common], help="diagnostic de la chaîne d'import")
    imports.set_defaults(run=cmd_imports)
    display = sub.add_parser("display", parents=[sub_common], help="sortie affichée par canal")
    display_sub = display.add_subparsers(dest="display_action", required=True)
    display_sub.add_parser("get", parents=[sub_common], help="lire les sorties câblé et réseau")
    display_set = display_sub.add_parser("set", parents=[sub_common], help="basculer un canal")
    display_set.add_argument("channel", choices=("cable", "network"))
    display_set.add_argument("output", choices=("kiosk", "cinema", "radio"))
    display.set_defaults(run=cmd_display)

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
        client = Client(host, port, out, _timeout(args))
        return args.run(client, out, args)
    except CliError as exc:
        if out.json and exc.payload is not None:
            print(json.dumps(exc.payload, ensure_ascii=False, indent=2))
        print(f"bobine : {exc}", file=sys.stderr)
        return exc.code
    except KeyboardInterrupt:
        return 130
    except (TypeError, AttributeError, KeyError, IndexError, ValueError) as exc:
        # Réponse 200 de forme inattendue (vide, `null`, champ absent) : un message, pas une traceback.
        out.log(1, f"{type(exc).__name__} : {exc}")
        print(f"bobine : réponse inattendue de Bobine ({type(exc).__name__}). Relancez avec -v pour le détail ; "
              "la version de la commande et celle du serveur diffèrent peut-être.", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
