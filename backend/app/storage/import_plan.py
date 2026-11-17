"""Plan d'un import depuis un support : unités, fichiers retenus, doublons écartés."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from app.api.contract import STORAGE_IMPORT_KINDS
from app.storage import library, paths
from app.storage.verified_copy import TransferError


@dataclass
class UnitFile:
    rel: str
    absolute: str
    size: int
    mtime_ns: int


@dataclass
class Unit:
    kind: str
    title: str
    files: list[UnitFile]
    key: str

    @property
    def total(self) -> int:
        return sum(f.size for f in self.files)


@dataclass
class Plan:
    units: list[Unit] = field(default_factory=list)
    skipped: list[dict[str, str]] = field(default_factory=list)
    truncated: bool = False

    @property
    def total_bytes(self) -> int:
        return sum(u.total for u in self.units)

    @property
    def total_files(self) -> int:
        return sum(len(u.files) for u in self.units)


KIND_TO_MEDIA = dict(zip(STORAGE_IMPORT_KINDS, ({"video"}, {"audio"}, {"audio"})))


JOB_KIND = {"video": "video", "radio": "radio", "audio_course": "audio"}


def _file(root: str, rel: str, absolute: str) -> UnitFile | None:
    try:
        st = os.stat(absolute)
    except OSError:
        return None
    return UnitFile(rel, absolute, st.st_size, st.st_mtime_ns)


def plan_import(root: str, entries: list[dict[str, str]], kind: str, source_id: str, db=None, force: bool = False) -> Plan:
    """Transforme la sélection (fichiers/dossiers) en unités d'import d'UNE nature (`video`, `audio_course`, `radio`)."""
    if kind not in KIND_TO_MEDIA:
        raise TransferError("bad_kind", "Nature d'import inconnue.", 400)
    plan = Plan()
    seen: set[str] = set()
    for entry in entries:
        rel = paths.clean_rel_path(entry.get("path"))
        absolute = paths.resolve_within(root, rel)
        if kind == "audio_course" and os.path.isdir(absolute):
            walked = paths.walk_media(root, [rel], KIND_TO_MEDIA[kind])
            plan.truncated |= walked.truncated
            files = [f for f in (_file(root, r, a) for r, a, _, _ in walked.files) if f]
            if not files:
                plan.skipped.append({"path": rel, "reason": "no_media"})
                continue
            title = os.path.basename(absolute.rstrip("/")) or "Cours importé"
            title = title.replace("_", " ").replace("-", " ").strip() or "Cours importé"
            if rel in seen:
                continue
            seen.add(rel)
            mtime = max(f.mtime_ns for f in files)
            if db is not None and not force and library.already_imported(db, source_id, rel, sum(f.size for f in files), mtime, kind):
                plan.skipped.append({"path": rel, "reason": "already_imported"})
                continue
            plan.units.append(Unit(kind, title, files, rel))
            continue
        walked = paths.walk_media(root, [rel], KIND_TO_MEDIA[kind])
        plan.truncated |= walked.truncated
        if not walked.files:
            plan.skipped.append({"path": rel, "reason": "no_media"})
        for r, a, _, _ in walked.files:
            if r in seen:
                continue
            seen.add(r)
            f = _file(root, r, a)
            if f is None:
                plan.skipped.append({"path": r, "reason": "unreadable"})
                continue
            if db is not None and not force and library.already_imported(db, source_id, r, f.size, f.mtime_ns, kind):
                plan.skipped.append({"path": r, "reason": "already_imported"})
                continue
            title = os.path.splitext(os.path.basename(a))[0].replace("_", " ").replace("-", " ").strip()
            plan.units.append(Unit(kind, title or os.path.basename(a), [f], r))
    return plan
