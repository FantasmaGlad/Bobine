"""Chemins sûrs et exploration d'arborescence d'un support (logique pure : seul `os` est utilisé).

Garanties :

* le client n'envoie qu'un chemin RELATIF au support ; il est nettoyé (`clean_rel_path`) puis résolu
  (`resolve_within`) : pas de `..`, pas de chemin absolu, pas d'octet nul, profondeur bornée ;
* un lien symbolique n'est suivi que s'il reste DANS le volume et sur le même périphérique (un montage
  imbriqué ou un lien vers `/etc` est ignoré, pas suivi) ;
* parcours borné (profondeur, nombre d'entrées, nombre de fichiers) et paginé : aucune réponse ne peut
  devenir énorme, aucun décodage de média n'a lieu pendant la navigation.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Iterator

MAX_REL_LENGTH = 4096
MAX_DEPTH = 16
MAX_SCAN_ENTRIES = 20_000      # entrées examinées par dossier
MAX_PAGE = 500
MAX_WALK_DEPTH = 12
MAX_WALK_FILES = 20_000

# Mêmes ensembles que les importeurs (un test le vérifie) : le support peut en contenir d'autres, ils ne sont pas proposés.
VIDEO_EXTENSIONS = frozenset({".mp4", ".m4v", ".mkv", ".avi", ".mov"})
AUDIO_EXTENSIONS = frozenset({
    ".mp3", ".m4a", ".aac", ".ogg", ".oga", ".opus", ".flac", ".wav", ".wma", ".aiff", ".aif", ".aifc", ".ape", ".alac",
    ".wv", ".mka", ".m4b", ".ac3",
})  # = formats audio de la radio et des cours audio, hors .mp4/.webm (conteneurs vidéo)
IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp"})
SUBTITLE_EXTENSIONS = frozenset({".srt", ".vtt"})

_HIDDEN_NAMES = frozenset({
    "$recycle.bin", "system volume information", "lost+found", "__macosx", "thumbs.db", "desktop.ini",
    "found.000", ".trashes", ".spotlight-v100", ".fseventsd", ".trash",
})


class PathError(Exception):
    """Chemin refusé ; `code` est stable (traduit par l'interface), `status` est le code HTTP."""

    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def media_kind(name: str) -> str | None:
    ext = os.path.splitext(name)[1].lower()
    if ext in VIDEO_EXTENSIONS:
        return "video"
    if ext in AUDIO_EXTENSIONS:
        return "audio"
    if ext in IMAGE_EXTENSIONS:
        return "image"
    if ext in SUBTITLE_EXTENSIONS:
        return "subtitle"
    return None


def is_hidden(name: str) -> bool:
    lowered = name.lower()
    return name.startswith(".") or lowered in _HIDDEN_NAMES or lowered.startswith(".trash-") or name.startswith("._")


def clean_rel_path(rel: str | None) -> str:
    """Chemin relatif normalisé (séparateur `/`, sans `.` ni segments vides) ; lève `PathError` sinon."""
    if rel is None or rel == "":
        return ""
    if "\x00" in rel or "\\" in rel:
        raise PathError("bad_path", "Chemin invalide.")
    if len(rel) > MAX_REL_LENGTH:
        raise PathError("bad_path", "Chemin trop long.")
    if rel.startswith("/") or (len(rel) > 1 and rel[1] == ":"):
        raise PathError("bad_path", "Chemin absolu refusé : seul un chemin relatif au support est accepté.")
    parts: list[str] = []
    for segment in rel.split("/"):
        if segment in ("", "."):
            continue
        if segment == "..":
            raise PathError("bad_path", "Le chemin ne peut pas remonter hors du support.")
        parts.append(segment)
    if len(parts) > MAX_DEPTH:
        raise PathError("bad_path", "Chemin trop profond.")
    return "/".join(parts)


def _real_root(root: str) -> str:
    return os.path.realpath(root)


def resolve_within(root: str, rel: str | None) -> str:
    """Chemin absolu réel de `rel` sous `root`, garanti DANS le volume (liens suivis seulement s'ils y restent)."""
    cleaned = clean_rel_path(rel)
    real_root = _real_root(root)
    candidate = os.path.realpath(os.path.join(real_root, cleaned)) if cleaned else real_root
    try:
        inside = os.path.commonpath([real_root, candidate]) == real_root
    except ValueError:
        inside = False
    if not inside:
        raise PathError("outside_volume", "Ce chemin sort du support.", 403)
    try:
        if os.stat(candidate).st_dev != os.stat(real_root).st_dev:
            raise PathError("outside_volume", "Ce chemin traverse un autre montage.", 403)
    except FileNotFoundError:
        raise PathError("not_found", "Dossier ou fichier introuvable sur le support.", 404)
    except OSError as exc:
        raise PathError("io_error", f"Lecture impossible : {exc.strerror or exc}", 502)
    return candidate


def to_rel(root: str, absolute: str) -> str:
    return os.path.relpath(absolute, _real_root(root)).replace(os.sep, "/")


@dataclass
class Entry:
    name: str
    type: str  # dir | file
    size: int | None
    mtime: float | None
    media: str | None = None
    hidden: bool = False


@dataclass
class Listing:
    path: str
    parent: str | None
    entries: list[Entry]
    total: int
    offset: int
    limit: int
    truncated: bool  # plus de MAX_SCAN_ENTRIES entrées : la liste est incomplète
    skipped_links: int = 0


def list_directory(
    root: str,
    rel: str | None = "",
    *,
    offset: int = 0,
    limit: int = 200,
    show_hidden: bool = False,
    media_only: bool = False,
) -> Listing:
    """Contenu paginé d'un dossier du support : dossiers d'abord, puis fichiers, tri insensible à la casse."""
    cleaned = clean_rel_path(rel)
    directory = resolve_within(root, cleaned)
    if not os.path.isdir(directory):
        raise PathError("not_a_directory", "Ce chemin n'est pas un dossier.", 400)
    limit = max(1, min(int(limit), MAX_PAGE))
    offset = max(0, int(offset))
    real_root = _real_root(root)
    root_dev = os.stat(real_root).st_dev

    names: list[tuple[str, bool, bool]] = []  # nom, est un dossier, caché
    skipped_links = 0
    truncated = False
    try:
        with os.scandir(directory) as it:
            for index, entry in enumerate(it):
                if index >= MAX_SCAN_ENTRIES:
                    truncated = True
                    break
                hidden = is_hidden(entry.name)
                if hidden and not show_hidden:
                    continue
                try:
                    if entry.is_symlink():
                        target = os.path.realpath(entry.path)
                        if os.path.commonpath([real_root, target]) != real_root or os.stat(target).st_dev != root_dev:
                            skipped_links += 1
                            continue
                        is_dir = os.path.isdir(target)
                    else:
                        is_dir = entry.is_dir(follow_symlinks=False)
                except (OSError, ValueError):
                    skipped_links += 1
                    continue
                if media_only and not is_dir and media_kind(entry.name) in (None, "subtitle"):
                    continue
                names.append((entry.name, is_dir, hidden))
    except PermissionError:
        raise PathError("permission_denied", "Accès refusé à ce dossier.", 403)
    except OSError as exc:
        raise PathError("io_error", f"Lecture impossible : {exc.strerror or exc}", 502)

    names.sort(key=lambda n: (not n[1], n[0].casefold()))
    page = names[offset:offset + limit]
    entries: list[Entry] = []
    for name, is_dir, hidden in page:
        full = os.path.join(directory, name)
        size = mtime = None
        try:
            st = os.stat(full)
            size = None if is_dir else st.st_size
            mtime = st.st_mtime
        except OSError:
            pass
        entries.append(Entry(name, "dir" if is_dir else "file", size, mtime, None if is_dir else media_kind(name), hidden))
    parent = None if not cleaned else "/".join(cleaned.split("/")[:-1])
    return Listing(cleaned, parent, entries, len(names), offset, limit, truncated, skipped_links)


@dataclass
class WalkResult:
    files: list[tuple[str, str, int, str]] = field(default_factory=list)  # (rel, absolu, taille, nature)
    truncated: bool = False
    skipped: int = 0


def walk_media(root: str, rels: list[str], kinds: set[str]) -> WalkResult:
    """Fichiers média sélectionnés (fichiers ou dossiers, récursif borné) ; ordre stable, sans doublon."""
    real_root = _real_root(root)
    root_dev = os.stat(real_root).st_dev
    result = WalkResult()
    seen: set[str] = set()

    def add(absolute: str) -> None:
        kind = media_kind(absolute)
        if kind is None or kind not in kinds:
            return
        try:
            size = os.stat(absolute).st_size
        except OSError:
            result.skipped += 1
            return
        rel = to_rel(root, absolute)
        if rel in seen:
            return
        seen.add(rel)
        if len(result.files) >= MAX_WALK_FILES:
            result.truncated = True
            return
        result.files.append((rel, absolute, size, kind))

    def walk(directory: str, depth: int) -> None:
        if depth > MAX_WALK_DEPTH or result.truncated:
            return
        try:
            entries = sorted(os.scandir(directory), key=lambda e: e.name.casefold())
        except OSError:
            result.skipped += 1
            return
        for entry in entries:
            if is_hidden(entry.name):
                continue
            try:
                if entry.is_symlink():
                    target = os.path.realpath(entry.path)
                    if os.path.commonpath([real_root, target]) != real_root or os.stat(target).st_dev != root_dev:
                        result.skipped += 1
                        continue
                if entry.is_dir():
                    walk(entry.path, depth + 1)
                elif entry.is_file():
                    add(entry.path)
            except (OSError, ValueError):
                result.skipped += 1

    for rel in rels:
        absolute = resolve_within(root, rel)
        if os.path.isdir(absolute):
            walk(absolute, 0)
        elif os.path.isfile(absolute):
            add(absolute)
    return result


def iter_chunks(path: str, chunk: int = 4 * 1024 * 1024) -> Iterator[bytes]:
    with open(path, "rb") as handle:
        while True:
            data = handle.read(chunk)
            if not data:
                return
            yield data


def safe_dest_name(name: str) -> str:
    """Nom de fichier assaini pour une écriture sur le support (export) : pas de séparateur, pas de caractère de contrôle."""
    cleaned = "".join(c for c in name if c.isprintable() and c not in '/\\:*?"<>|').strip().strip(".")
    return cleaned[:200] or "fichier"


def unique_dest(directory: str, name: str) -> str:
    """Chemin libre dans `directory` (suffixe ` (2)`, ` (3)`… : jamais d'écrasement d'un fichier existant du support)."""
    stem, ext = os.path.splitext(name)
    candidate = os.path.join(directory, name)
    counter = 2
    while os.path.exists(candidate):
        candidate = os.path.join(directory, f"{stem} ({counter}){ext}")
        counter += 1
    return candidate


def inside(base: str, target: str) -> bool:
    """Vrai si `target` (réel) est sous `base` (réel)."""
    try:
        return os.path.commonpath([os.path.realpath(base), os.path.realpath(target)]) == os.path.realpath(base)
    except ValueError:
        return False



def ensure_dir_within(root: str, rel: str | None) -> str:
    """Crée (si besoin) le dossier relatif `rel` sous `root`, segment par segment, en vérifiant chaque étape :
    jamais de création hors du volume, jamais à travers un lien symbolique qui en sortirait."""
    cleaned = clean_rel_path(rel)
    current = ""
    for segment in cleaned.split("/") if cleaned else []:
        candidate = f"{current}/{segment}" if current else segment
        try:
            resolve_within(root, candidate)
        except PathError as exc:
            if exc.code != "not_found":
                raise
            parent = resolve_within(root, current)
            try:
                os.mkdir(os.path.join(parent, segment))
            except FileExistsError:
                pass
            except OSError as err:
                raise PathError("io_error", f"Création du dossier impossible : {err.strerror or err}", 502)
        current = candidate
    return resolve_within(root, cleaned)
