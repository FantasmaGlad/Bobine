"""Résumé borné du contenu d'un support (ce qui sera EFFACÉ) : espace utilisé, nombre de fichiers, dossiers à la racine,
médias que Bobine reconnaît. Lecture seule, sans suivre les liens symboliques, avec plafond de nombre et de durée."""

from __future__ import annotations

import os
import time
from typing import Any

from app.storage.paths import media_kind

MAX_ENTRIES = 40_000
MAX_SECONDS = 4.0
ROOT_LIST = 12
_SKIP_ROOT = frozenset({"System Volume Information", "$RECYCLE.BIN", "lost+found", ".Trash-1000", ".Spotlight-V100", ".fseventsd"})


def summarize(root: str, *, max_entries: int = MAX_ENTRIES, max_seconds: float = MAX_SECONDS, clock=time.monotonic) -> dict[str, Any]:
    deadline = clock() + max_seconds
    files = dirs = 0
    media = {"video": 0, "audio": 0}
    bytes_seen = 0
    top: list[dict[str, Any]] = []
    truncated = False
    try:
        top_entries = sorted(os.scandir(root), key=lambda e: e.name.lower())
    except OSError:
        return {"readable": False}
    for entry in top_entries:
        if entry.name in _SKIP_ROOT:
            continue
        is_dir = entry.is_dir(follow_symlinks=False)
        if len(top) < ROOT_LIST:
            top.append({"name": entry.name, "type": "dir" if is_dir else "file"})
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                for entry in it:
                    if files + dirs >= max_entries or clock() > deadline:
                        truncated = True
                        stack.clear()
                        break
                    if current == root and entry.name in _SKIP_ROOT:
                        continue
                    try:
                        if entry.is_symlink():
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            dirs += 1
                            stack.append(entry.path)
                        elif entry.is_file(follow_symlinks=False):
                            files += 1
                            kind = media_kind(entry.name)
                            if kind in media:
                                media[kind] += 1
                            try:
                                bytes_seen += entry.stat(follow_symlinks=False).st_size
                            except OSError:
                                pass
                    except OSError:
                        continue
        except OSError:
            continue
    return {
        "readable": True, "files": files, "dirs": dirs, "bytes": bytes_seen, "truncated": truncated,
        "root": top, "root_truncated": len(top_entries) > ROOT_LIST, "media": media,
    }
