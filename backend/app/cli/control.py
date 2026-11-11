"""Commandes d'action : lecture, diagnostic, mise à jour, ouverture d'une page, appel direct d'une route."""

from __future__ import annotations

import argparse
import json
import posixpath
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .client import Client
from .core import EXIT_ERROR, EXIT_OK, EXIT_USAGE, CliError, Output, parse_params, segment


def _apply_fix(client: Client, fix: dict) -> list[str]:
    """Applique une correction décrite par le diagnostic (`fix`) par les routes de l'interface ; renvoie ce qui a été fait."""
    action = fix.get("action")
    if action == "cancel_import_jobs":
        done = []
        for job_id in fix.get("job_ids") or []:
            client.request("DELETE", f"/api/import-jobs/{segment(job_id)}", accept_status=frozenset({404}))
            done.append(f"import {str(job_id)[:8]} annulé")
        return done
    if action == "set_settings":
        client.request("PUT", "/api/settings", body=fix.get("settings") or {})
        return ["réglage " + ", ".join(f"{k}={v}" for k, v in (fix.get("settings") or {}).items())]
    raise CliError(f"correction inconnue : {action!r} (version de la commande différente de celle du serveur ?)", EXIT_ERROR)


def cmd_diagnose(client: Client, out: Output, args: argparse.Namespace) -> int:
    report = client.request("GET", "/api/diagnostics/system")
    colors = {"critical": "red", "warning": "yellow", "info": "dim"}
    lines = [f"État : {report['status']}"]
    fixable = [p for p in report["problems"] if p.get("fix")]
    for problem in report["problems"]:
        lines.append(f"  {out.paint(problem['severity'], colors[problem['severity']])} {problem['code']} : {problem['message']}")
        lines.append(f"    remède : {problem['remedy']}")
        if problem.get("fix"):
            lines.append("    corrigeable par --auto-fix --yes" if args.auto_fix else "    corrigeable : bobine diagnose --auto-fix")
    if out.verbosity >= 1:
        lines += [f"  sonde {c['name']} : {c['status']}" + (f" ({c['detail']})" if c.get("detail") else "") for c in report["checks"]]
    if args.auto_fix:
        if not fixable:
            lines.append("Rien à corriger automatiquement.")
        elif not args.yes:
            lines.append(f"{len(fixable)} correction(s) possible(s) : relancez avec --yes pour les appliquer.")
        else:
            applied = []
            for problem in fixable:
                applied += [f"{problem['code']} : {step}" for step in _apply_fix(client, problem["fix"])]
            lines += [f"corrigé : {step}" for step in applied]
            report = client.request("GET", "/api/diagnostics/system")
            lines.append(f"État après correction : {report['status']} ({len(report['problems'])} constat(s) restant(s))")
    out.result(report, "\n".join(lines))
    return EXIT_OK if report["status"] == "ok" else EXIT_ERROR


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


# Routes que `bobine api` refuse toujours : leur commande dédiée demande la confirmation et fait les vérifications (sinon
# elles ne sont pas offertes par la ligne de commande).
DANGEROUS_ROUTES = (
    (re.compile(r"POST /api/settings/system/(reset|uninstall|reset-data|restart)"), "irréversible : interface, ou install.sh --uninstall"),
    (re.compile(r"POST /api/settings/backup/restore"), "bobine settings restore FICHIER --yes"),
    (re.compile(r"POST /api/storage/format/execute"), "assistant de formatage de l'interface"),
    (re.compile(r"POST /api/updates/apply"), "bobine update apply --yes"),
    (re.compile(r"POST /api/config/apply"), "bobine config apply DOSSIER --yes"),
)
_API_PATH = re.compile(r"^/api/[A-Za-z0-9_./{}%~-]+$")


def cmd_api(client: Client, out: Output, args: argparse.Namespace) -> int:
    """`bobine api METHODE /api/chemin` : n'importe quelle route de l'API, pour ce qu'aucune commande ne couvre encore."""
    method, path = args.method.upper(), args.path
    # Le serveur décode le chemin une fois (`%61pply` -> `apply`) : la liste des routes dangereuses
    # doit donc être comparée au chemin décodé et normalisé, pas à la chaîne brute.
    canonical = posixpath.normpath(urllib.parse.unquote(path))
    if not _API_PATH.match(path) or ".." in path.split("/") or ".." in canonical.split("/"):
        raise CliError("chemin invalide : attendu /api/... sans ?, # ni .. (les paramètres passent par --query)", EXIT_USAGE)
    for pattern, hint in DANGEROUS_ROUTES:
        if pattern.fullmatch(f"{method} {canonical}"):
            raise CliError(f"{method} {path} n'est pas offerte par bobine api ({hint}).", EXIT_USAGE)
    if method != "GET" and not args.yes:
        raise CliError(f"{method} {path} modifie Bobine : relancer avec --yes pour confirmer.", EXIT_USAGE)
    body = None
    if args.body is not None:
        try:
            raw = sys.stdin.read() if args.body == "-" else Path(args.body[1:]).read_text(encoding="utf-8") if args.body.startswith("@") else args.body
        except (OSError, UnicodeDecodeError) as exc:
            raise CliError(f"corps JSON illisible : {exc}", EXIT_USAGE) from exc
        try:
            body = json.loads(raw)
        except ValueError as exc:
            raise CliError(f"corps JSON illisible : {exc}", EXIT_USAGE) from exc
    query = parse_params(args.query or [])
    payload = client.request(method, path, query=query or None, body=body)
    out.json = True  # la réponse de l'API, telle quelle, sur stdout
    out.result(payload)
    return EXIT_OK


OPEN_PAGES = {"admin": "/", "grid": "/grid", "cinema": "/cinema"}


def cmd_open(client: Client, out: Output, args: argparse.Namespace) -> int:
    """Ouvre une page dans le navigateur, sur le port réel de cette machine (raccourcis du bureau, sans port écrit en dur)."""
    import webbrowser

    if args.page not in OPEN_PAGES:
        raise CliError(f"page inconnue : {args.page} ({', '.join(OPEN_PAGES)}).", EXIT_USAGE)
    url = client.base + OPEN_PAGES[args.page]
    if not webbrowser.open(url):
        raise CliError(f"aucun navigateur n'a pu être ouvert ; adresse : {url}")
    out.result({"url": url}, url)
    return EXIT_OK
