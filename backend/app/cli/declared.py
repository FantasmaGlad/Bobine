"""Commandes déclaratives (`specs`) et imports de fichiers avec suivi des tâches."""

from __future__ import annotations

import argparse
import math
import time
from pathlib import Path
from typing import Any

from app.cli.specs import SPECS, Spec, UsageError
from app.utils.media_formats import ARCHIVE as ARCHIVE_EXTENSIONS

from .client import Client
from .core import EXIT_ERROR, EXIT_OK, EXIT_USAGE, CliError, Output


def _run_spec(client: Client, out: Output, args: argparse.Namespace) -> int:
    spec: Spec = args.spec
    if spec.needs_one_of and not any(getattr(args, name, None) not in (None, False) for name in spec.needs_one_of):
        options = ", ".join("--" + name.replace("_", "-") for name in spec.needs_one_of)
        raise CliError(f"indiquer au moins une option : {options}", EXIT_USAGE)
    if spec.confirm and not args.yes:
        raise CliError(spec.confirm.format(**vars(args)) + " Relancer avec --yes pour confirmer.", EXIT_USAGE)
    try:
        call = spec.request(client, args)
    except UsageError as exc:
        raise CliError(str(exc), EXIT_USAGE) from exc
    payload = client.request(call.method, call.path, body=call.body, query=call.query)
    out.result(payload, spec.human(payload, args))
    return EXIT_OK


def add_spec_commands(sub: Any, sub_common: argparse.ArgumentParser) -> None:
    """Ajoute au parser chaque `Spec` : sous-commande de sa commande (créée si elle n'existe pas encore)."""
    for spec in SPECS:
        command = sub.choices.get(spec.command)
        if command is None:
            command = sub.add_parser(spec.command, parents=[sub_common], help=f"{spec.command} : voir « bobine {spec.command} --help »")
        actions = next((a for a in command._actions if isinstance(a, argparse._SubParsersAction)), None)
        if actions is None:
            actions = command.add_subparsers(dest=f"{spec.command.replace('-', '_')}_action", required=True)
        parser = actions.add_parser(spec.action, parents=[sub_common], help=spec.help)
        for argument in spec.arguments:
            argument.add_to(parser)
        if spec.confirm:
            parser.add_argument("--yes", action="store_true", help="confirmer (sinon rien n'est modifié)")
        parser.set_defaults(run=_run_spec, spec=spec)


IMPORT_FAMILIES = {
    # famille -> (route d'un envoi, route d'une archive zip, champ du fichier, un envoi par fichier, champs de formulaire)
    "library": ("/api/videos/upload", "/api/videos/upload-zip", "file", True, ("title", "program", "release", "description")),
    "audio": ("/api/audio/upload", "/api/audio/upload-zip", "files", False, ("title", "program", "release")),
    "radio-library": ("/api/radio/tracks/upload", "/api/radio/tracks/upload-zip", "files", False, ()),
    "backgrounds": ("/api/backgrounds/upload", "/api/backgrounds/upload-zip", "file", True, ("title",)),
}
FINISHED_STAGES = ("done", "error", "cancelled")


def cmd_import(client: Client, out: Output, args: argparse.Namespace) -> int:
    """`bobine <famille> import FICHIER...` : envoi d'un ou plusieurs fichiers, avec attente facultative des tâches."""
    route, zip_route, field_name, one_per_file, form = IMPORT_FAMILIES[args.command]
    files = [Path(raw) for raw in args.files]
    for file in files:
        if not file.is_file():
            raise CliError(f"fichier introuvable : {file}", EXIT_USAGE)
    fields = {name: getattr(args, name) for name in form if getattr(args, name, None) is not None}
    if args.command == "audio" and not fields.get("title"):
        raise CliError("--title est obligatoire pour un cours audio", EXIT_USAGE)
    if fields and one_per_file and len(files) > 1:
        raise CliError("titre, programme, release et description ne s'appliquent qu'à un seul fichier : envoyer les autres séparément", EXIT_USAGE)
    requests: list[tuple[str, list[tuple[str, Path]]]] = []
    if zip_route and len(files) == 1 and files[0].name.lower().endswith(ARCHIVE_EXTENSIONS):
        requests.append((zip_route, [("file", files[0])]))
    elif one_per_file:
        requests += [(route, [(field_name, file)]) for file in files]
    else:
        requests.append((route, [(field_name, file) for file in files]))
    accepted = []
    for path, parts in requests:
        answer = client.upload(path, parts, fields)
        job = (answer or {}).get("job_id") or (answer or {}).get("id")
        accepted.append({"files": [file.name for _, file in parts], "job": job, "answer": answer})
    results = accepted
    if args.wait:
        results = _wait_for_jobs(client, out, accepted, args.wait_timeout)
    failed = [r for r in results if r.get("stage") in ("error", "cancelled")]
    lines = [f"{', '.join(r['files'])} : " + (f"tâche {r['job']}" + (f", {r['stage']}" if r.get("stage") else "") if r["job"] else "importé") for r in results]
    out.result({"imports": results}, "\n".join(lines))
    return EXIT_ERROR if failed else EXIT_OK


def _wait_for_jobs(client: Client, out: Output, accepted: list[dict], timeout: float) -> list[dict]:
    """Interroge la file d'import jusqu'à la fin de chaque tâche ; une tâche absente de la liste est considérée comme finie."""
    if not (timeout > 0 and math.isfinite(timeout)):
        raise CliError(f"délai d'attente invalide : {timeout!r} (secondes, > 0).", EXIT_USAGE)
    deadline = time.monotonic() + timeout
    pending = {item["job"]: item for item in accepted if item["job"]}
    while pending:
        jobs = {job.get("id"): job for job in client.request("GET", "/api/import-jobs") or []}
        for job_id in list(pending):
            job = jobs.get(job_id)
            if job is None:
                pending.pop(job_id).setdefault("stage", "done")
            elif job.get("stage") in FINISHED_STAGES:
                finished = pending.pop(job_id)
                finished["stage"], finished["message"] = job["stage"], job.get("error") or job.get("message")
            else:
                out.log(0, f"{job_id[:8]}  {job.get('stage')}  {job.get('progress_percent') or 0} %")
        if pending and time.monotonic() > deadline:
            raise CliError(f"{len(pending)} tâche(s) encore en cours après {timeout:g} s (elles continuent : bobine imports list).", EXIT_ERROR)
        if pending:
            time.sleep(1.0)
    return accepted


def add_import_commands(sub: Any, sub_common: argparse.ArgumentParser) -> None:
    for family, (_, zip_route, _, one_per_file, form) in IMPORT_FAMILIES.items():
        command = sub.choices.get(family)
        if command is None:
            command = sub.add_parser(family, parents=[sub_common], help=f"{family} : voir « bobine {family} --help »")
        actions = next((a for a in command._actions if isinstance(a, argparse._SubParsersAction)), None) or command.add_subparsers(
            dest=f"{family.replace('-', '_')}_action", required=True)
        parser = actions.add_parser("import", parents=[sub_common], help=(
            "envoyer une archive .zip ou des fichiers" if zip_route else "envoyer un ou plusieurs fichiers"))
        parser.add_argument("files", nargs="+", metavar="fichier")
        for name in form:
            parser.add_argument(f"--{name}")
        parser.add_argument("--wait", action="store_true", help="attendre la fin des tâches d'import (code de sortie 1 si l'une échoue)")
        parser.add_argument("--wait-timeout", type=float, default=3600.0, metavar="SECONDES")
        parser.set_defaults(run=cmd_import)
