"""Téléversement par morceaux reprenable (lot F2 du plan de compatibilité
Firefox, docs/PLAN-COMPATIBILITE-FIREFOX.md).

Pourquoi : jusqu'ici, un fichier vidéo ou une archive ZIP partait en UNE seule
requête `multipart/form-data` de plusieurs Go. Une coupure Wi-Fi à 95 %
obligeait à tout recommencer, une requête aussi longue est fragile face aux
intermédiaires et pèse sur la mémoire/le disque temporaire du navigateur
(Firefox pour Android compris). Le client découpe désormais le fichier en
morceaux (`Blob.slice`), les envoie un par un (`PATCH` avec `Upload-Offset`) et
peut REPRENDRE à l'octet près après une coupure — y compris après un
rechargement de page, grâce à l'empreinte du fichier.

Protocole (inspiré de tus, volontairement minimal) :
  POST   /api/uploads            {filename, size, fingerprint?} -> {upload_id, offset, chunk_size}
  GET    /api/uploads/{id}       -> {offset, size, complete}
  PATCH  /api/uploads/{id}       en-tête Upload-Offset, corps binaire -> {offset, complete}
  DELETE /api/uploads/{id}       abandon
Puis le point d'entrée d'import habituel (`/api/videos/upload`, etc.) est
appelé avec le champ de formulaire `upload_id` au lieu du fichier : il reprend
le fichier déjà reçu sans le recopier (`take_staged_upload`).
"""

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
# Marge d'espace disque exigée au-delà de la taille annoncée : le fichier
# reçu est ensuite lu par ffprobe/ffmpeg, qui peut produire une copie normalisée.
FREE_SPACE_FACTOR = 1.1

_locks_guard = threading.Lock()
_active: set[str] = set()


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
        raise HTTPException(status_code=404, detail="Téléversement introuvable ou expiré")


def create_session(filename: str, size: int, fingerprint: str | None) -> Session:
    if size < 0:
        raise HTTPException(status_code=400, detail="Taille de fichier invalide")
    purge_stale()
    if fingerprint:
        # Même fichier déjà en cours de transfert (rechargement de page,
        # coupure) : on reprend la session existante au lieu d'en créer une.
        for meta_file in staging_dir().glob("*.json"):
            try:
                existing = _read(meta_file.stem)
            except HTTPException:
                continue
            if existing.fingerprint == fingerprint and existing.size == size and not existing.complete:
                return existing
    free = _free_bytes()
    if size * FREE_SPACE_FACTOR > free:
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
    return session


def _free_bytes() -> int:
    import shutil
    return shutil.disk_usage(staging_dir()).free


def get_session(upload_id: str) -> Session:
    return _read(upload_id)


def acquire(upload_id: str) -> None:
    """Un seul `PATCH` à la fois par session : deux écritures concurrentes à
    des positions différentes corrompraient le fichier (409 pour le second)."""
    with _locks_guard:
        if upload_id in _active:
            raise HTTPException(status_code=409, detail="Un transfert est déjà en cours pour ce fichier")
        _active.add(upload_id)


def release(upload_id: str) -> None:
    with _locks_guard:
        _active.discard(upload_id)


def abort(upload_id: str) -> None:
    _validate_id(upload_id)
    for path in (_part_path(upload_id), _meta_path(upload_id)):
        try:
            path.unlink()
        except OSError:
            pass


def purge_stale() -> int:
    """Supprime les sessions abandonnées depuis plus de 24 h (appelé à chaque
    création et au démarrage) — un transfert interrompu ne doit pas occuper
    indéfiniment plusieurs Go dans le dossier temporaire."""
    removed = 0
    now = time.time()
    for path in staging_dir().glob("*"):
        try:
            if path.name.endswith((".part", ".json")) and now - path.stat().st_mtime > STALE_AFTER_SECONDS:
                path.unlink()
                removed += 1
        except OSError:
            pass
    return removed


def take_staged_upload(upload_id: str, forced_suffix: str | None = None) -> tuple[str, str]:
    """Consomme une session terminée : renvoie (chemin du fichier, nom d'origine).
    Le fichier est renommé (extension d'origine conservée) et appartient dès
    lors à l'appelant — le job d'import le supprime à la fin, comme pour un
    fichier reçu en multipart."""
    session = _read(upload_id)
    if not session.complete:
        raise HTTPException(
            status_code=409,
            detail=f"Téléversement incomplet ({session.offset}/{session.size} octets) — reprenez le transfert.",
        )
    suffix = forced_suffix or Path(session.filename).suffix.lower()
    final = staging_dir() / f"{upload_id}{suffix}"
    os.replace(_part_path(upload_id), final)
    _meta_path(upload_id).unlink(missing_ok=True)
    return str(final), session.filename


def receive_single_upload(file: UploadFile | None, upload_id: str | None, forced_suffix: str | None = None) -> tuple[str, str]:
    """Point d'entrée commun des handlers d'import à fichier unique : soit un
    fichier déjà téléversé par morceaux (`upload_id`, aucune recopie), soit un
    `multipart` classique (copié dans un fichier temporaire, comportement
    historique conservé pour les clients simples et les anciennes versions)."""
    import shutil

    if upload_id:
        return take_staged_upload(upload_id, forced_suffix)
    if file is None or not file.filename:
        raise HTTPException(status_code=400, detail="Aucun fichier reçu")
    suffix = forced_suffix or Path(file.filename).suffix.lower()
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            shutil.copyfileobj(file.file, temp_file)
            return temp_file.name, file.filename
    except Exception as e:
        logger.error(f"Erreur lors de la réception de l'upload : {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))
