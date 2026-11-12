"""Téléversement par morceaux reprenable."""

import json
import logging
import os
import re
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, UploadFile

logger = logging.getLogger(__name__)

CHUNK_SIZE = 8 * 1024 * 1024
STALE_AFTER_SECONDS = 24 * 3600
_ID_RE = re.compile(r"^[0-9a-f]{32}$")
FREE_SPACE_FACTOR = 1.1

_locks_guard = threading.Lock()
_active: set[str] = set()


def short_id(upload_id: str | None) -> str:
    """Identifiant abrégé pour les journaux (8 premiers caractères) ; une valeur qui n'a pas la forme d'un identifiant n'est jamais recopiée telle quelle (entrée du client)."""
    return upload_id[:8] if upload_id and _ID_RE.match(upload_id) else "invalide"


def staging_dir() -> Path:
    path = Path(tempfile.gettempdir()) / "bobine-uploads"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _validate_id(upload_id: str) -> str:
    if not _ID_RE.match(upload_id or ""):
        raise HTTPException(status_code=404, detail="Téléversement introuvable")
    return upload_id


def _part_path(upload_id: str) -> Path:
    return staging_dir() / f"{upload_id}.part"


def _meta_path(upload_id: str) -> Path:
    return staging_dir() / f"{upload_id}.json"


@dataclass
class Session:
    upload_id: str
    filename: str
    size: int
    fingerprint: str | None
    created_at: float

    @property
    def offset(self) -> int:
        try:
            return _part_path(self.upload_id).stat().st_size
        except OSError:
            return 0

    @property
    def complete(self) -> bool:
        return self.offset == self.size


def _read(upload_id: str) -> Session:
    _validate_id(upload_id)
    try:
        meta = json.loads(_meta_path(upload_id).read_text(encoding="utf-8"))
        return Session(upload_id, meta["filename"], int(meta["size"]), meta.get("fingerprint"), float(meta["created_at"]))
    except (OSError, ValueError, KeyError):
        logger.warning("Upload %s : session introuvable ou expirée", short_id(upload_id))
        raise HTTPException(status_code=404, detail="Téléversement introuvable ou expiré")


def create_session(filename: str, size: int, fingerprint: str | None) -> Session:
    if size < 0:
        raise HTTPException(status_code=400, detail="Taille de fichier invalide")
    purge_stale()
    if fingerprint:
        for meta_file in staging_dir().glob("*.json"):
            try:
                existing = _read(meta_file.stem)
            except HTTPException:
                continue
            if existing.fingerprint == fingerprint and existing.size == size and not existing.complete:
                logger.info(
                    "Upload %s repris : %d/%d octets déjà reçus (même fichier re-sélectionné)",
                    short_id(existing.upload_id), existing.offset, size,
                )
                return existing
    free = _free_bytes()
    if size * FREE_SPACE_FACTOR > free:
        logger.warning(
            "Upload refusé : espace disque insuffisant (%d Mo libres dans %s, %d Mo annoncés)",
            free // 1_048_576, staging_dir(), size // 1_048_576,
        )
        raise HTTPException(
            status_code=507,
            detail=f"Espace disque insuffisant sur le serveur ({free // 1_048_576} Mo libres, {size // 1_048_576} Mo requis).",
        )
    upload_id = uuid.uuid4().hex
    session = Session(upload_id, Path(filename).name or "fichier", size, fingerprint, time.time())
    _meta_path(upload_id).write_text(
        json.dumps({
            "filename": session.filename, "size": size,
            "fingerprint": fingerprint, "created_at": session.created_at,
        }),
        encoding="utf-8",
    )
    _part_path(upload_id).touch()
    logger.info(
        "Upload %s créé : %d octets, extension %s, dossier %s",
        short_id(upload_id), size, Path(session.filename).suffix.lower() or "(aucune)", staging_dir(),
    )
    return session


def _free_bytes() -> int:
    import shutil
    return shutil.disk_usage(staging_dir()).free


def get_session(upload_id: str) -> Session:
    return _read(upload_id)


def acquire(upload_id: str) -> None:
    """Un seul `PATCH` à la fois par session : deux écritures concurrentes à des positions différentes corrompraient le fichier (409 pour le second)."""
    with _locks_guard:
        if upload_id in _active:
            raise HTTPException(status_code=409, detail="Un transfert est déjà en cours pour ce fichier")
        _active.add(upload_id)


def release(upload_id: str) -> None:
    with _locks_guard:
        _active.discard(upload_id)


def abort(upload_id: str) -> None:
    _validate_id(upload_id)
    try:
        received = _part_path(upload_id).stat().st_size
    except OSError:
        received = 0
    logger.info("Upload %s abandonné par le client (%d octets reçus, fichiers supprimés)", short_id(upload_id), received)
    for path in (_part_path(upload_id), _meta_path(upload_id)):
        try:
            path.unlink()
        except OSError:
            pass


def purge_stale() -> int:
    """Supprime les sessions abandonnées depuis plus de 24 h (appelé à chaque création et au démarrage) — un transfert interrompu ne doit pas occuper indéfiniment plusieurs Go dans le dossier temporaire."""
    removed = 0
    now = time.time()
    for path in staging_dir().glob("*"):
        try:
            if path.name.endswith((".part", ".json")) and now - path.stat().st_mtime > STALE_AFTER_SECONDS:
                path.unlink()
                removed += 1
        except OSError:
            pass
    if removed:
        logger.info("Uploads périmés purgés : %d fichier(s) de plus de %d h supprimé(s)", removed, STALE_AFTER_SECONDS // 3600)
    return removed


def take_staged_upload(upload_id: str, forced_suffix: str | None = None) -> tuple[str, str]:
    """Consomme une session terminée : renvoie (chemin du fichier, nom d'origine)."""
    session = _read(upload_id)
    if not session.complete:
        logger.warning(
            "Upload %s : import demandé alors que le transfert est incomplet (%d/%d octets)",
            short_id(upload_id), session.offset, session.size,
        )
        raise HTTPException(
            status_code=409,
            detail=f"Téléversement incomplet ({session.offset}/{session.size} octets) — reprenez le transfert.",
        )
    suffix = forced_suffix or Path(session.filename).suffix.lower()
    final = staging_dir() / f"{upload_id}{suffix}"
    os.replace(_part_path(upload_id), final)
    _meta_path(upload_id).unlink(missing_ok=True)
    logger.info("Upload %s remis à l'import : %d octets", short_id(upload_id), session.size)
    return str(final), session.filename


def receive_single_upload(file: UploadFile | None, upload_id: str | None, forced_suffix: str | None = None) -> tuple[str, str]:
    """Point d'entrée commun des handlers d'import à fichier unique."""
    import shutil

    if upload_id:
        return take_staged_upload(upload_id, forced_suffix)
    if file is None or not file.filename:
        raise HTTPException(status_code=400, detail="Aucun fichier reçu")
    suffix = forced_suffix or Path(file.filename).suffix.lower()
    temp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_path = temp_file.name
            shutil.copyfileobj(file.file, temp_file)
            return temp_path, file.filename
    except Exception as e:
        if temp_path is not None:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
        logger.error(f"Erreur lors de la réception de l'upload : {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))
