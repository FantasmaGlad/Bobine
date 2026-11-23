"""Les espaces de médias visuels de Bobine."""
from __future__ import annotations

from app.config import settings
from app.models import Background

from .collection import AssetCollection

BACKGROUNDS = AssetCollection(
    key="backgrounds", model=Background,
    directory=lambda: settings.backgrounds_dir, watch_directory=lambda: settings.backgrounds_watch_dir,
    file_prefix="bg", label="Fond animé", plural="Fonds animés", archive_label="d'ambiance", job_kind="background",
    imported_event="background_imported", route_prefix="/api/backgrounds", id_param="background_id",
    not_found="Fond animé non trouvé", deleted="Fond animé supprimé avec succès",
)

COLLECTIONS: tuple[AssetCollection, ...] = (BACKGROUNDS,)
