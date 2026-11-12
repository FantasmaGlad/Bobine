"""Commandes de configuration : export et application des fichiers, réglages, sauvegarde et restauration."""

from __future__ import annotations

import argparse
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from .client import Client
from .core import EXIT_ERROR, EXIT_OK, EXIT_USAGE, CliError, Output, parse_params

CONFIG_FAMILIES = ("outputs", "library", "playlists", "schedule", "radio")


def _read_documents(paths: list[str]) -> dict[str, Any]:
    files: dict[str, Any] = {}
    for raw in paths:
        path = Path(raw)
        targets = sorted(path.rglob("*.json")) if path.is_dir() else [path]
        for target in targets:
            name = target.relative_to(path).as_posix() if path.is_dir() else target.name
            base = path if path.is_dir() else target.parent
            if "/" not in name and base.name in CONFIG_FAMILIES and name != "settings.json":
                name = f"{base.name}/{name}"
            if name in files:
                raise CliError(f"deux fichiers nommés {name} : l'un écraserait l'autre (le nom désigne le type de réglage).", EXIT_USAGE)
            try:
                files[name] = json.loads(target.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise CliError(f"{target} illisible : {exc}", EXIT_USAGE) from exc
    if not files:
        raise CliError("aucun fichier JSON à appliquer", EXIT_USAGE)
    return files


def _checked_export_name(name: object) -> str:
    text = str(name)
    normalized = text.replace("\\", "/")
    if (
        not text
        or any(ord(ch) < 32 or ord(ch) == 127 for ch in text)
        or normalized.startswith("/")
        or re.match(r"^[A-Za-z]:", normalized)
        or ".." in normalized.split("/")
    ):
        raise CliError(f"nom de fichier refusé par le serveur : {name!r}", EXIT_ERROR)
    return text


def cmd_config(client: Client, out: Output, args: argparse.Namespace) -> int:
    if args.config_action == "export":
        if args.name:
            document = client.request("GET", "/api/config/export/" + urllib.parse.quote(args.name.replace("\\", "/"), safe="/"),
                                      accept_status=frozenset({404}))
            if not isinstance(document, dict) or "kind" not in document:
                raise CliError(f"fichier inconnu : {args.name}", EXIT_USAGE)
            exported = {args.name: document}
        else:
            exported = client.request("GET", "/api/config/export")["files"]
        if not isinstance(exported, dict):
            raise CliError("réponse d'export invalide : objet « files » attendu.", EXIT_ERROR)
        if args.directory:
            target = Path(args.directory)
            try:
                target.mkdir(parents=True, exist_ok=True)
                for name, document in exported.items():
                    relative = name if args.name else _checked_export_name(name)
                    path = target / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            except OSError as exc:
                raise CliError(f"écriture impossible dans {target} : {exc}", EXIT_ERROR) from exc
            out.result({"written": sorted(exported), "directory": str(target)}, f"{len(exported)} fichier(s) écrit(s) dans {target}")
        else:
            out.json = True
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
    body = {k: ("true" if v else "false") if isinstance(v, bool) else v for k, v in changes.items()}
    saved = client.request("PUT", "/api/settings", body=body)
    message = "Réglage(s) enregistré(s) : " + ", ".join(body)
    if isinstance(saved, dict) and saved.get("language_restart_required"):
        message += "\nLa langue s'applique au redémarrage de Bobine."
    out.result(saved if saved is not None else body, message)
    return EXIT_OK


def cmd_backup(client: Client, out: Output, args: argparse.Namespace) -> int:
    destination = Path(args.file)
    size = client.download("/api/settings/backup/export", destination)
    out.result({"file": str(destination), "bytes": size}, f"Sauvegarde écrite dans {destination} ({size} octets).")
    return EXIT_OK


def cmd_restore(client: Client, out: Output, args: argparse.Namespace) -> int:
    source = Path(args.file)
    if not source.is_file():
        raise CliError(f"fichier introuvable : {source}", EXIT_USAGE)
    if not args.yes:
        raise CliError("La restauration remplace la base de données et redémarre Bobine. Relancer avec --yes pour confirmer.", EXIT_USAGE)
    answer = client.upload("/api/settings/backup/restore", [("file", source)])
    out.result(answer, "Sauvegarde restaurée : Bobine redémarre.")
    return EXIT_OK
