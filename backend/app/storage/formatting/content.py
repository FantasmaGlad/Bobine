"""Résumé borné du contenu d'un support (ce qui sera EFFACÉ) : espace utilisé, nombre de fichiers, dossiers à la racine, médias que Bobine reconnaît."""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from app.storage.paths import media_kind

logger = logging.getLogger(__name__)

MAX_ENTRIES = 40_000
MAX_SECONDS = 4.0
ROOT_LIST = 12
_SKIP_ROOT = frozenset({"System Volume Information", "$RECYCLE.BIN", "lost+found", ".Trash-1000", ".Spotlight-V100", ".fseventsd"})


class _Tally:
    def __init__(self, root: str, max_entries: int, deadline: float, clock) -> None:
        self.root, self.max_entries, self.deadline, self.clock = root, max_entries, deadline, clock
        self.files = self.dirs = self.bytes = 0
        self.media = {"video": 0, "audio": 0}
        self.truncated = False

    def walk(self) -> None:
        stack = [self.root]
        while stack and not self.truncated:
            current = stack.pop()
            try:
                with os.scandir(current) as it:
                    self._scan(current, it, stack)
            except OSError as exc:
                logger.debug("Dossier illisible pendant le résumé du contenu : %s", exc)

    def _scan(self, current: str, entries, stack: list[str]) -> None:
        for entry in entries:
            if self.files + self.dirs >= self.max_entries or self.clock() > self.deadline:
                self.truncated = True
                return
            if current == self.root and entry.name in _SKIP_ROOT:
                continue
            try:
                self._count(entry, stack)
            except OSError as exc:
                logger.debug("Entrée illisible pendant le résumé du contenu : %s", exc)

    def _count(self, entry: os.DirEntry, stack: list[str]) -> None:
        if entry.is_symlink():
            return
        if entry.is_dir(follow_symlinks=False):
            self.dirs += 1
            stack.append(entry.path)
        elif entry.is_file(follow_symlinks=False):
            self.files += 1
            kind = media_kind(entry.name)
            if kind in self.media:
                self.media[kind] += 1
            try:
                self.bytes += entry.stat(follow_symlinks=False).st_size
            except OSError as exc:
                logger.debug("Taille illisible pendant le résumé du contenu : %s", exc)


def _root_listing(entries: list[os.DirEntry]) -> list[dict[str, Any]]:
    shown = [entry for entry in entries if entry.name not in _SKIP_ROOT][:ROOT_LIST]
    return [{"name": entry.name, "type": "dir" if entry.is_dir(follow_symlinks=False) else "file"} for entry in shown]


def summarize(root: str, *, max_entries: int = MAX_ENTRIES, max_seconds: float = MAX_SECONDS, clock=time.monotonic) -> dict[str, Any]:
    deadline = clock() + max_seconds
    try:
        top_entries = sorted(os.scandir(root), key=lambda e: e.name.lower())
    except OSError:
        return {"readable": False}
    top = _root_listing(top_entries)
    tally = _Tally(root, max_entries, deadline, clock)
    tally.walk()
    return {
        "readable": True, "files": tally.files, "dirs": tally.dirs, "bytes": tally.bytes, "truncated": tally.truncated,
        "root": top, "root_truncated": len(top_entries) > ROOT_LIST, "media": tally.media,
    }
