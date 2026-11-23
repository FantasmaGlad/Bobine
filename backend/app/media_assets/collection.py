"""Description d'un espace de médias visuels : dossiers, préfixes, libellés et modèle."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class AssetCollection:
    key: str
    model: type
    directory: Callable[[], str]
    watch_directory: Callable[[], str]
    file_prefix: str
    label: str
    plural: str
    archive_label: str
    job_kind: str
    imported_event: str
    route_prefix: str
    id_param: str
    not_found: str
    deleted: str
