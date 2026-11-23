"""Les espaces de médias visuels de Bobine."""
from __future__ import annotations

from app.config import settings
from app.models import Background, Visual

from .collection import AssetCollection

BACKGROUNDS = AssetCollection(
    key="backgrounds", model=Background,
    directory=lambda: settings.backgrounds_dir, watch_directory=lambda: settings.backgrounds_watch_dir,
    file_prefix="bg", label="Fond animé", plural="Fonds animés", archive_label="d'ambiance", job_kind="background",
    imported_event="background_imported", route_prefix="/api/backgrounds", id_param="background_id",
    not_found="Fond animé non trouvé", deleted="Fond animé supprimé avec succès",
)

VISUALS = AssetCollection(
    key="visuals", model=Visual,
    directory=lambda: settings.visuals_dir, watch_directory=lambda: settings.visuals_watch_dir,
    file_prefix="vis", label="Visuel", plural="Visuels", archive_label="de visuels", job_kind="visual",
    imported_event="visual_imported", route_prefix="/api/visuals", id_param="visual_id",
    not_found="Visuel non trouvé", deleted="Visuel supprimé avec succès",
)

COLLECTIONS: tuple[AssetCollection, ...] = (BACKGROUNDS, VISUALS)
