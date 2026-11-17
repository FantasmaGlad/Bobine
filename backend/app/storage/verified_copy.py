"""Copie vérifiée et reprenable entre un support et le stockage local : espace, zone de transit, empreintes, export."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from app.storage import paths

logger = logging.getLogger(__name__)


COPY_CHUNK = 4 * 1024 * 1024


RESERVE_BYTES = 1024**3


SPACE_FACTOR = 1.1


STALE_PART_SECONDS = 7 * 24 * 3600


class TransferError(Exception):
    def __init__(self, code: str, message: str, status: int = 400, **extra: Any):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.extra = extra


class Cancelled(Exception):
    """Transfert annulé par l'utilisateur."""


def staging_root() -> Path:
    from app.config import settings

    root = Path(settings.media_dir).parent / "tmp" / "storage-import"
    (root / "parts").mkdir(parents=True, exist_ok=True)
    return root


def purge_staging(max_age: float = STALE_PART_SECONDS) -> int:
    """Au démarrage : dossiers de travail orphelins supprimés ; `.part` plus vieux que `max_age` supprimés (les récents restent pour la reprise)."""
    root = staging_root()
    removed = 0
    now = time.time()
    for entry in root.iterdir():
        if entry.name == "parts":
            for part in entry.iterdir():
                try:
                    if now - part.stat().st_mtime > max_age:
                        part.unlink()
                        removed += 1
                except OSError:
                    pass
        elif entry.is_dir():
            shutil.rmtree(entry, ignore_errors=True)
            removed += 1
    return removed


def free_bytes(directory: Path | None = None) -> int:
    return shutil.disk_usage(directory or staging_root()).free


def needed_bytes(total: int) -> int:
    return int(total * SPACE_FACTOR) + RESERVE_BYTES


def check_space(total: int, already: int = 0, free: int | None = None) -> None:
    """Lève `insufficient_space` si le disque local ne peut pas accueillir `total` octets (moins ce qui est déjà copié)."""
    available = free_bytes() if free is None else free
    need = needed_bytes(max(0, total - already))
    if available < need:
        raise TransferError(
            "insufficient_space",
            "Espace libre insuffisant sur le stockage local.",
            409,
            needed_bytes=need,
            free_bytes=available,
        )


def _hasher_of_prefix(path: str, length: int) -> "hashlib._Hash":
    digest = hashlib.sha256()
    remaining = length
    with open(path, "rb") as handle:
        while remaining > 0:
            block = handle.read(min(COPY_CHUNK, remaining))
            if not block:
                break
            digest.update(block)
            remaining -= len(block)
    return digest


def _sha_of_prefix(path: str, length: int) -> str:
    return _hasher_of_prefix(path, length).hexdigest()


def _sha_of_file(path: str) -> str:
    return _sha_of_prefix(path, os.path.getsize(path))


def part_path_for(source_id: str, rel: str, size: int, mtime_ns: int) -> Path:
    key = hashlib.sha1(f"{source_id}|{rel}|{size}|{mtime_ns}".encode()).hexdigest()[:24]
    return staging_root() / "parts" / f"{key}.part"


def _source_stat(src: str, verb: str = "impossible") -> os.stat_result:
    try:
        return os.stat(src)
    except OSError as exc:
        raise TransferError("source_io", f"Lecture de la source {verb} : {exc.strerror or exc}", 502) from exc


def discard(*paths: Path) -> None:
    for path in paths:
        try:
            path.unlink()
        except OSError:
            pass


def _resume_point(src: str, part: Path, meta: Path, size: int, mtime_ns: int, verify_source: bool):
    try:
        saved = json.loads(meta.read_text())
        have = part.stat().st_size
        if saved.get("size") == size and saved.get("mtime_ns") == mtime_ns and 0 < have <= size and verify_source:
            hasher = _hasher_of_prefix(str(part), have)
            if _sha_of_prefix(src, have) == hasher.hexdigest():
                return hasher, have
    except (OSError, ValueError):
        pass
    return hashlib.sha256(), 0


def _copy_blocks(src: str, part: Path, offset: int, digest, chunk: int, is_cancelled, on_bytes) -> int:
    copied = offset
    with open(src, "rb") as reader, open(part, "ab" if offset else "wb") as writer:
        reader.seek(offset)
        while True:
            if is_cancelled():
                raise Cancelled()
            try:
                block = reader.read(chunk)
            except OSError as exc:
                raise TransferError("source_io", f"Lecture de la source interrompue : {exc.strerror or exc}", 502) from exc
            if not block:
                break
            try:
                writer.write(block)
            except OSError as exc:
                raise TransferError("dest_io", f"Écriture locale impossible : {exc.strerror or exc}", 507) from exc
            digest.update(block)
            copied += len(block)
            on_bytes(len(block))
        writer.flush()
        os.fsync(writer.fileno())
    return copied


def copy_verified(
    src: str,
    dest: str,
    *,
    part: Path,
    verify_source: bool = True,
    resume: bool = True,
    is_cancelled: Callable[[], bool] = lambda: False,
    on_bytes: Callable[[int], None] = lambda n: None,
    chunk: int = COPY_CHUNK,
) -> dict[str, Any]:
    """Copie `src` vers `dest` (via `part`) avec reprise et vérification d'intégrité."""
    before = _source_stat(src)
    size, mtime_ns = before.st_size, before.st_mtime_ns
    meta = Path(str(part) + ".json")
    digest, offset = hashlib.sha256(), 0
    if resume and part.exists() and meta.exists():
        digest, offset = _resume_point(src, part, meta, size, mtime_ns, verify_source)
    if offset == 0:
        discard(part, meta)
    meta.write_text(json.dumps({"size": size, "mtime_ns": mtime_ns}))
    if offset:
        on_bytes(offset)
    try:
        copied = _copy_blocks(src, part, offset, digest, chunk, is_cancelled, on_bytes)
    except Cancelled:
        discard(part, meta)
        raise
    after = _source_stat(src)
    if copied != size or after.st_size != size or after.st_mtime_ns != mtime_ns:
        discard(part, meta)
        raise TransferError("source_changed", "Le fichier a changé pendant la copie : relancez l'import.", 409)
    expected = digest.hexdigest()
    if _sha_of_file(str(part)) != expected or part.stat().st_size != size:
        discard(part, meta)
        raise TransferError("verify_failed", "La copie ne correspond pas à l'original (vérification SHA-256 échouée).", 502)
    os.replace(part, dest)
    discard(meta)
    return {"size": size, "sha256": expected, "resumed_from": offset}


def _fsync_dir(directory: str) -> None:
    try:
        fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError as exc:
        logger.warning("fsync du dossier %s impossible : %s", directory, exc)
    finally:
        os.close(fd)


def export_file(
    src: str,
    dest_dir: str,
    name: str,
    *,
    is_cancelled: Callable[[], bool] = lambda: False,
    on_bytes: Callable[[int], None] = lambda n: None,
    chunk: int = COPY_CHUNK,
) -> dict[str, Any]:
    """Copie `src` (local) dans `dest_dir` (support monté en écriture) : nom libre, fichier temporaire puis renommage atomique, fsync, relecture et comparaison SHA-256."""
    dest = paths.unique_dest(dest_dir, paths.safe_dest_name(name))
    tmp = os.path.join(dest_dir, f".bobine-{uuid.uuid4().hex[:10]}.part")
    digest = hashlib.sha256()
    written = 0
    try:
        with open(src, "rb") as reader, open(tmp, "wb") as writer:
            while True:
                if is_cancelled():
                    raise Cancelled()
                block = reader.read(chunk)
                if not block:
                    break
                try:
                    writer.write(block)
                except OSError as exc:
                    raise TransferError("dest_io", f"Écriture sur le support impossible : {exc.strerror or exc}", 507) from exc
                digest.update(block)
                written += len(block)
                on_bytes(len(block))
            writer.flush()
            os.fsync(writer.fileno())
        if os.path.getsize(tmp) != written or _sha_of_file(tmp) != digest.hexdigest():
            raise TransferError("verify_failed", "La copie sur le support ne correspond pas à l'original.", 502)
        os.replace(tmp, dest)
        _fsync_dir(dest_dir)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
    return {"path": dest, "size": written, "sha256": digest.hexdigest()}
