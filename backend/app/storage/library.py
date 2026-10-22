"""Accès base de données du stockage externe : bibliothèques enregistrées, remappage des chemins, index.

Fonctions SYNCHRONES (à appeler dans un thread depuis le service asynchrone). Règle centrale : le chemin
`file_path` d'un média externe est soit son chemin réel courant (support en ligne), soit un chemin
d'attente `external://<uuid>/<rel>` (support absent) — unique et jamais résolvable sur le disque, donc
deux supports successifs au même point de montage ne peuvent jamais se confondre.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import (
    AudioCourse,
    AudioPlaylistItem,
    AudioTrack,
    ExternalVolume,
    PlaylistItem,
    RadioPlaylistItem,
    RadioTrack,
    StorageImport,
    Video,
)
from app.storage import longevity
from app.storage.availability import placeholder_path
from app.storage.types import Volume

logger = logging.getLogger(__name__)

# (modèle, nom de la nature) des tables qui portent des médias externes.
_MEDIA_MODELS = ((Video, "video"), (AudioTrack, "audio"), (RadioTrack, "radio"))


def global_defaults(db: Session) -> dict[str, Any]:
    from app.models import Setting

    row = db.query(Setting).filter(Setting.key == "storage_defaults").first()
    try:
        raw = json.loads(row.value) if row else {}
    except ValueError:
        raw = {}
    return longevity.normalize_settings(raw if isinstance(raw, dict) else {})


def save_global_defaults(db: Session, values: dict[str, Any]) -> dict[str, Any]:
    from app.models import Setting

    merged = longevity.normalize_settings(values, base=global_defaults(db))
    row = db.query(Setting).filter(Setting.key == "storage_defaults").first()
    payload = json.dumps(merged)
    if row is None:
        db.add(Setting(key="storage_defaults", value=payload))
    else:
        row.value = payload
    db.commit()
    return merged


def settings_of(db: Session, lib: ExternalVolume | None) -> dict[str, Any]:
    """Réglages effectifs : défauts globaux, surchargés par ceux du support enregistré."""
    base = global_defaults(db)
    if lib is None or not lib.settings:
        return base
    try:
        raw = json.loads(lib.settings)
    except ValueError:
        raw = {}
    return longevity.normalize_settings(raw if isinstance(raw, dict) else {}, base=base)


def get_by_uuid(db: Session, fs_uuid: str | None) -> ExternalVolume | None:
    if not fs_uuid:
        return None
    return db.query(ExternalVolume).filter(ExternalVolume.fs_uuid == fs_uuid).first()


def all_libraries(db: Session) -> list[ExternalVolume]:
    return db.query(ExternalVolume).order_by(ExternalVolume.id).all()


def register(db: Session, volume: Volume, nickname: str | None = None) -> ExternalVolume:
    if not volume.fs_uuid:
        raise ValueError("uuid_missing")
    lib = get_by_uuid(db, volume.fs_uuid)
    if lib is None:
        lib = ExternalVolume(fs_uuid=volume.fs_uuid)
        db.add(lib)
    lib.label = volume.label
    lib.fstype = volume.fstype
    lib.size_bytes = volume.size_bytes
    lib.kind = volume.kind
    lib.enabled = True
    if nickname is not None:
        lib.nickname = nickname.strip()[:60] or None
    lib.last_seen_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(lib)
    return lib


def stats(db: Session, storage_id: int) -> dict[str, int]:
    return {
        "videos": db.query(Video).filter(Video.storage_id == storage_id).count(),
        "audio_tracks": db.query(AudioTrack).filter(AudioTrack.storage_id == storage_id).count(),
        "radio_tracks": db.query(RadioTrack).filter(RadioTrack.storage_id == storage_id).count(),
    }


def mark_all_offline(db: Session) -> int:
    """Au démarrage : tout média externe passe en chemin d'attente (un chemin conservé de la session précédente
    pourrait désigner, au même point de montage, un AUTRE support). Le premier instantané remappe les supports présents."""
    return _apply(db, {lib.id: None for lib in all_libraries(db)})


def apply_mapping(db: Session, online: dict[int, str], previous: dict[int, str]) -> bool:
    """Remappe les chemins des seuls supports dont l'état a changé ; vrai si quelque chose a bougé."""
    changed: dict[int, str | None] = {}
    for lib in all_libraries(db):
        if online.get(lib.id) != previous.get(lib.id):
            changed[lib.id] = online.get(lib.id)
    if not changed:
        return False
    _apply(db, changed)
    return True


def _apply(db: Session, targets: dict[int, str | None]) -> int:
    libs = {lib.id: lib for lib in all_libraries(db)}
    moved = 0
    # Les supports qui partent d'abord : libère leurs chemins avant d'attribuer ceux des supports qui arrivent.
    for storage_id in sorted(targets, key=lambda i: targets[i] is not None):
        lib = libs.get(storage_id)
        if lib is None:
            continue
        root = targets[storage_id]
        for model, _ in _MEDIA_MODELS:
            rows = db.query(model.id, model.rel_path).filter(model.storage_id == storage_id).all()
            mappings = [
                {
                    "id": row_id,
                    "file_path": os.path.join(root, *rel.split("/")) if root else placeholder_path(lib.fs_uuid, rel),
                }
                for row_id, rel in rows
                if rel
            ]
            if mappings:
                db.bulk_update_mappings(model, mappings)
                moved += len(mappings)
        if root:
            lib.last_mount_path = root
            lib.last_seen_at = datetime.now(timezone.utc)
        db.commit()
    return moved


def purge_index(db: Session, storage_id: int) -> dict[str, int]:
    """Retire de la base les médias indexés d'un support (jamais les fichiers du support) et leurs fichiers INTERNES
    (miniatures, pochettes) ; nettoie les éléments de playlists qui les référençaient."""
    removed = {"videos": 0, "audio_tracks": 0, "radio_tracks": 0, "audio_courses": 0}
    videos = db.query(Video).filter(Video.storage_id == storage_id).all()
    ids = [v.id for v in videos]
    if ids:
        db.query(PlaylistItem).filter(PlaylistItem.video_id.in_(ids)).delete(synchronize_session=False)
    for video in videos:
        _unlink_internal(video.thumbnail_path)
        _unlink_internal(video.web_path)
        db.delete(video)
        removed["videos"] += 1
    tracks = db.query(AudioTrack).filter(AudioTrack.storage_id == storage_id).all()
    track_ids = [t.id for t in tracks]
    course_ids = {t.audio_course_id for t in tracks}
    if track_ids:
        db.query(AudioPlaylistItem).filter(AudioPlaylistItem.audio_track_id.in_(track_ids)).delete(synchronize_session=False)
    for track in tracks:
        db.delete(track)
        removed["audio_tracks"] += 1
    db.flush()
    for course_id in course_ids:
        if db.query(AudioTrack).filter(AudioTrack.audio_course_id == course_id).count() == 0:
            course = db.query(AudioCourse).filter(AudioCourse.id == course_id).first()
            if course is not None:
                db.delete(course)
                removed["audio_courses"] += 1
    radios = db.query(RadioTrack).filter(RadioTrack.storage_id == storage_id).all()
    radio_ids = [r.id for r in radios]
    if radio_ids:
        db.query(RadioPlaylistItem).filter(RadioPlaylistItem.radio_track_id.in_(radio_ids)).delete(synchronize_session=False)
    for radio in radios:
        _unlink_internal(radio.cover_path)
        radio.tags = []
        db.delete(radio)
        removed["radio_tracks"] += 1
    db.commit()
    return removed


def _unlink_internal(path: str | None) -> None:
    if not path:
        return
    try:
        os.remove(path)
    except OSError:
        pass


def indexed_lookup(db: Session, storage_id: int, rels: list[str]) -> dict[str, dict[str, Any]]:
    """Pour une page de l'explorateur : lesquels de ces chemins sont déjà indexés (+ durée connue, sans rien décoder)."""
    if not rels:
        return {}
    found: dict[str, dict[str, Any]] = {}
    for model, kind in _MEDIA_MODELS:
        for rel, duration, row_id in db.query(model.rel_path, model.duration_seconds, model.id).filter(
            model.storage_id == storage_id, model.rel_path.in_(rels)
        ):
            found[rel] = {"indexed": True, "kind": kind, "id": row_id, "duration_seconds": duration}
    return found


def add_bytes_written(db: Session, storage_id: int, amount: int) -> int:
    lib = db.query(ExternalVolume).filter(ExternalVolume.id == storage_id).first()
    if lib is None:
        return 0
    lib.bytes_written = (lib.bytes_written or 0) + max(0, int(amount))
    db.commit()
    return lib.bytes_written


def already_imported(db: Session, source_id: str, rel: str, size: int, mtime_ns: int, kind: str) -> bool:
    """Vrai si ce fichier du support a déjà été importé ET que le média local existe encore (supprimé : on peut le réimporter)."""
    row = (
        db.query(StorageImport)
        .filter(
            StorageImport.source_id == source_id,
            StorageImport.rel_path == rel,
            StorageImport.size_bytes == size,
            StorageImport.mtime_ns == mtime_ns,
            StorageImport.kind == kind,
        )
        .first()
    )
    if row is None:
        return False
    model = {"video": Video, "audio_course": AudioCourse, "radio": RadioTrack}.get(kind)
    if model is None or row.local_id is None:
        return True
    if db.query(model.id).filter(model.id == row.local_id).first() is None:
        db.delete(row)
        db.commit()
        return False
    return True


def record_import(db: Session, source_id: str, rel: str, size: int, mtime_ns: int, kind: str, local_id: int | None) -> None:
    db.add(StorageImport(source_id=source_id, rel_path=rel, size_bytes=size, mtime_ns=mtime_ns, kind=kind, local_id=local_id))
    db.commit()
