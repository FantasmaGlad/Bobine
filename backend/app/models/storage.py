"""Supports externes enregistrés et imports depuis un support."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, utcnow


class ExternalVolume(Base):
    """Support externe enregistré comme « bibliothèque » : identifié par l'UUID de son système de fichiers (jamais par son point de montage, qui change à chaque branchement)."""
    __tablename__ = "external_volumes"

    id: Mapped[int] = mapped_column(primary_key=True)
    fs_uuid: Mapped[str] = mapped_column(unique=True)
    label: Mapped[str | None]
    nickname: Mapped[str | None]
    fstype: Mapped[str | None]
    size_bytes: Mapped[int | None]
    kind: Mapped[str] = mapped_column(default="other")
    enabled: Mapped[bool] = mapped_column(default=True)
    settings: Mapped[str | None] = mapped_column(Text)
    bytes_written: Mapped[int] = mapped_column(default=0)
    last_mount_path: Mapped[str | None]
    last_seen_at: Mapped[datetime | None]
    last_health: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class StorageImport(Base):
    """Trace d'un média déjà importé depuis un support (ou un appareil portable) vers le stockage local."""
    __tablename__ = "storage_imports"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[str] = mapped_column(index=True)
    rel_path: Mapped[str] = mapped_column(Text)
    size_bytes: Mapped[int]
    mtime_ns: Mapped[int]
    kind: Mapped[str]
    local_id: Mapped[int | None]
    imported_at: Mapped[datetime] = mapped_column(default=utcnow)
