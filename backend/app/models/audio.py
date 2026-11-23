"""Fonds, cours audio, pistes et playlists audio."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.utils.media_formats import BACKGROUND_IMAGE as IMAGE_EXTENSIONS

from .base import Base, ExternalMediaMixin, UidMixin, utcnow


class Background(UidMixin, Base):
    __uid_prefix__ = "bg"
    __tablename__ = "backgrounds"

    id: Mapped[int] = mapped_column(primary_key=True)
    file_path: Mapped[str] = mapped_column(unique=True)
    title: Mapped[str]
    duration_seconds: Mapped[float | None]
    thumbnail_path: Mapped[str | None]
    imported_at: Mapped[datetime] = mapped_column(default=utcnow)

    @property
    def is_image(self) -> bool:
        if not self.file_path:
            return False
        return Path(self.file_path).suffix.lower() in IMAGE_EXTENSIONS


class AudioCourse(UidMixin, Base):
    __uid_prefix__ = "crs"
    __tablename__ = "audio_courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    program: Mapped[str | None]
    release: Mapped[str | None]
    title: Mapped[str]
    background_id: Mapped[int | None] = mapped_column(ForeignKey("backgrounds.id", ondelete="SET NULL"))
    imported_at: Mapped[datetime] = mapped_column(default=utcnow)

    background: Mapped[Background | None] = relationship()
    tracks: Mapped[list["AudioTrack"]] = relationship(
        back_populates="course", order_by="AudioTrack.position", cascade="all, delete-orphan", passive_deletes=True
    )

    @property
    def background_thumbnail_path(self) -> str | None:
        return self.background.thumbnail_path if self.background else None

    @property
    def available(self) -> bool:
        """Vrai si au moins une piste est lisible ; `partially_available` signale les cours dont des pistes manquent."""
        return not self.tracks or any(t.available for t in self.tracks)

    @property
    def partially_available(self) -> bool:
        return any(not t.available for t in self.tracks) and any(t.available for t in self.tracks)

    @property
    def external(self) -> bool:
        return any(t.storage_id is not None for t in self.tracks)


class AudioTrack(UidMixin, ExternalMediaMixin, Base):
    __uid_prefix__ = "trk"
    __tablename__ = "audio_tracks"

    id: Mapped[int] = mapped_column(primary_key=True)
    audio_course_id: Mapped[int] = mapped_column(ForeignKey("audio_courses.id", ondelete="CASCADE"))
    number: Mapped[int | None]
    title: Mapped[str]
    file_path: Mapped[str] = mapped_column(unique=True)
    duration_seconds: Mapped[float | None]
    position: Mapped[int]
    background_id: Mapped[int | None] = mapped_column(ForeignKey("backgrounds.id", ondelete="SET NULL"), nullable=True)
    storage_id: Mapped[int | None] = mapped_column(ForeignKey("external_volumes.id", ondelete="SET NULL"), index=True)
    rel_path: Mapped[str | None]

    course: Mapped[AudioCourse] = relationship(back_populates="tracks")
    background: Mapped["Background | None"] = relationship()

    @property
    def background_title(self) -> str | None:
        return self.background.title if self.background else None

    @property
    def background_is_image(self) -> bool:
        if not self.background or not self.background.file_path:
            return False
        return Path(self.background.file_path).suffix.lower() in IMAGE_EXTENSIONS


class AudioPlaylist(UidMixin, Base):
    __uid_prefix__ = "apl"
    """Playlist spéciale composée de pistes individuelles piochées dans
    n'importe quel cours audio :
    une "édition mixée" est une séquence de PISTES (pas de cours entiers
    enchaînés) — un mix peut donc combiner des morceaux de RPM 101, 103 et
    110 dans n'importe quel ordre."""
    __tablename__ = "audio_playlists"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    items: Mapped[list["AudioPlaylistItem"]] = relationship(
        back_populates="playlist", order_by="AudioPlaylistItem.position", cascade="all, delete-orphan", passive_deletes=True
    )


class AudioPlaylistItem(Base):
    __tablename__ = "audio_playlist_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    playlist_id: Mapped[int] = mapped_column(ForeignKey("audio_playlists.id", ondelete="CASCADE"))
    audio_track_id: Mapped[int] = mapped_column(ForeignKey("audio_tracks.id", ondelete="CASCADE"))
    position: Mapped[int]
    background_id: Mapped[int | None] = mapped_column(ForeignKey("backgrounds.id", ondelete="SET NULL"))

    playlist: Mapped[AudioPlaylist] = relationship(back_populates="items")
    track: Mapped["AudioTrack"] = relationship()
    background: Mapped[Background | None] = relationship()
