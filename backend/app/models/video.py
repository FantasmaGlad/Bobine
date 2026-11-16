"""Vidéos, sous-titres, chapitres et playlists vidéo."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, ExternalMediaMixin, ImportSource, UidMixin, utcnow

if TYPE_CHECKING:
    from .runtime import CourseRating, PlaybackSession



class Video(UidMixin, ExternalMediaMixin, Base):
    __uid_prefix__ = "vid"
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(primary_key=True)
    file_path: Mapped[str] = mapped_column(unique=True)
    title: Mapped[str]
    program: Mapped[str | None]
    release: Mapped[str | None]
    duration_seconds: Mapped[float | None]
    width: Mapped[int | None]
    height: Mapped[int | None]
    codec: Mapped[str | None]
    thumbnail_path: Mapped[str | None]
    description: Mapped[str | None]
    audio_channels: Mapped[int | None]
    audio_codec: Mapped[str | None]
    fps: Mapped[float | None]
    bitrate_kbps: Mapped[int | None]
    pix_fmt: Mapped[str | None]
    web_path: Mapped[str | None]
    web_status: Mapped[str | None]
    chapters_source: Mapped[str | None] = mapped_column(Text, default=None)
    chapters_file: Mapped[str | None] = mapped_column(Text, default=None)
    imported_at: Mapped[datetime] = mapped_column(default=utcnow)
    source: Mapped[ImportSource]
    storage_id: Mapped[int | None] = mapped_column(ForeignKey("external_volumes.id", ondelete="SET NULL"), index=True)
    rel_path: Mapped[str | None]

    @property
    def web_issues(self) -> list[str]:
        from app.utils.web_profile import web_playback_issues

        return web_playback_issues(self.codec, self.pix_fmt, self.width, self.height, self.fps)

    @property
    def web_safe(self) -> bool:
        return not self.web_issues

    playlist_items: Mapped[list["PlaylistItem"]] = relationship(
        back_populates="video", cascade="all, delete-orphan", passive_deletes=True
    )
    ratings: Mapped[list["CourseRating"]] = relationship(back_populates="video", cascade="all, delete-orphan", passive_deletes=True)
    playback_sessions: Mapped[list["PlaybackSession"]] = relationship(back_populates="video", cascade="all, delete-orphan", passive_deletes=True)
    subtitles: Mapped[list["VideoSubtitle"]] = relationship(back_populates="video", cascade="all, delete-orphan", passive_deletes=True)
    chapters: Mapped[list["VideoChapter"]] = relationship(
        back_populates="video", cascade="all, delete-orphan", passive_deletes=True, order_by="VideoChapter.position"
    )


class VideoSubtitle(Base):
    __tablename__ = "video_subtitles"

    id: Mapped[int] = mapped_column(primary_key=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    language_code: Mapped[str] = mapped_column(Text, default="fr")
    language_label: Mapped[str] = mapped_column(Text, default="Français")
    file_path: Mapped[str] = mapped_column(Text)
    format: Mapped[str] = mapped_column(Text, default="vtt")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    video: Mapped["Video"] = relationship(back_populates="subtitles")


class VideoChapter(Base):
    __tablename__ = "video_chapters"

    id: Mapped[int] = mapped_column(primary_key=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(default=0)
    start_seconds: Mapped[float]
    end_seconds: Mapped[float | None]
    title: Mapped[str] = mapped_column(Text)

    video: Mapped["Video"] = relationship(back_populates="chapters")


class Playlist(UidMixin, Base):
    __uid_prefix__ = "pl"
    __tablename__ = "playlists"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    items: Mapped[list["PlaylistItem"]] = relationship(
        back_populates="playlist", order_by="PlaylistItem.position", cascade="all, delete-orphan", passive_deletes=True
    )


class PlaylistItem(Base):
    __tablename__ = "playlist_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    playlist_id: Mapped[int] = mapped_column(ForeignKey("playlists.id", ondelete="CASCADE"))
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"))
    position: Mapped[int]

    playlist: Mapped[Playlist] = relationship(back_populates="items")
    video: Mapped[Video] = relationship(back_populates="playlist_items")
