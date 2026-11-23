"""Base déclarative, identifiant stable et énumérations communes."""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import String, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.storage.availability import media_available
from app.utils.media_formats import BACKGROUND_IMAGE


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class UidMixin:
    """Identifiant stable, propre à l'objet et jamais modifié."""

    __uid_prefix__ = "x"
    uid: Mapped[str | None] = mapped_column(String(32), unique=True, index=True, nullable=True)



class ExternalMediaMixin:
    """Média éventuellement rangé sur un support externe : disponible seulement si ce support est branché."""

    @property
    def available(self) -> bool:
        return media_available(self.storage_id)

    @property
    def external(self) -> bool:
        return self.storage_id is not None


@event.listens_for(Base, "before_insert", propagate=True)
def _give_uid(mapper, connection, target) -> None:
    if isinstance(target, UidMixin) and not target.uid:
        from app.utils.uid import new_uid

        target.uid = new_uid(target.__uid_prefix__)


class ImportSource(str, enum.Enum):
    upload = "upload"
    watched_folder = "watched_folder"


class ScheduleType(str, enum.Enum):
    once = "once"
    recurring = "recurring"


class ScheduleTargetType(str, enum.Enum):
    video = "video"
    playlist = "playlist"
    radio_playlist = "radio_playlist"


class OverrideAction(str, enum.Enum):
    cancelled = "cancelled"
    replaced = "replaced"


class RadioCoverSource(str, enum.Enum):
    """Origine de la pochette d'un morceau radio : `id3` = extraite du fichier à l'import, `manual` = image fournie/remplacée depuis l'admin, `none` = pas de pochette."""
    id3 = "id3"
    manual = "manual"
    none = "none"


class RadioAnnouncementRuleType(str, enum.Enum):
    """Type de déclenchement d'un rappel : entre les morceaux (`every_n_tracks`), à intervalle régulier (`every_x_minutes`) ou à horaires fixes récurrents (`fixed_times`)."""
    every_n_tracks = "every_n_tracks"
    every_x_minutes = "every_x_minutes"
    fixed_times = "fixed_times"


class VisualAssetMixin:
    """Colonnes d'un média visuel (image, GIF ou vidéo courte), communes aux fonds animés et aux visuels diffusés."""

    id: Mapped[int] = mapped_column(primary_key=True)
    file_path: Mapped[str] = mapped_column(unique=True)
    title: Mapped[str]
    duration_seconds: Mapped[float | None]
    thumbnail_path: Mapped[str | None]
    imported_at: Mapped[datetime] = mapped_column(default=utcnow)

    @property
    def is_image(self) -> bool:
        return bool(self.file_path) and Path(self.file_path).suffix.lower() in BACKGROUND_IMAGE
