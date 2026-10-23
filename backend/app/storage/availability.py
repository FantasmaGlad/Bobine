"""Registre en mémoire des supports externes en ligne.

Une bibliothèque externe peut compter des milliers de médias : savoir si l'un d'eux est lisible NE
DOIT PAS coûter une entrée/sortie par ligne (un support débranché bloque `stat`). Le service de
stockage tient donc à jour ce dictionnaire `storage_id -> racine de montage` à chaque changement ;
`Video.available` & co. le lisent sans toucher au disque.

Module volontairement sans dépendance (importé par `models.py`)."""

from __future__ import annotations

import threading

PLACEHOLDER_PREFIX = "external:"

_lock = threading.Lock()
_online: dict[int, str] = {}


def set_online(mapping: dict[int, str]) -> None:
    """Remplace d'un bloc l'ensemble des supports en ligne (atomique pour les lecteurs)."""
    global _online
    with _lock:
        _online = dict(mapping)


def snapshot() -> dict[int, str]:
    with _lock:
        return dict(_online)


def is_online(storage_id: int | None) -> bool:
    return storage_id is not None and storage_id in _online


def media_available(storage_id: int | None) -> bool:
    """Un média local est toujours « disponible » (son absence reste un 404 comme avant) ; un média externe seulement support en ligne."""
    return storage_id is None or storage_id in _online


def mount_root(storage_id: int | None) -> str | None:
    return _online.get(storage_id) if storage_id is not None else None


def placeholder_path(fs_uuid: str, rel_path: str) -> str:
    """Chemin d'attente d'un média dont le support est absent : unique, jamais résolvable sur le disque."""
    return f"{PLACEHOLDER_PREFIX}//{fs_uuid}/{rel_path}"


def is_placeholder(path: object) -> bool:
    return str(path).startswith(PLACEHOLDER_PREFIX)
