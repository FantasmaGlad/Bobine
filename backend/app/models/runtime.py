"""État d'exécution, réglages, journal, notes et métriques."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, utcnow

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .video import Video



class PlaybackState(Base):
    """Mémorise une action différée en attente de reprise ou de relance manuelle depuis l'interface."""
    __tablename__ = "playback_state"

    id: Mapped[int] = mapped_column(primary_key=True)
    video_id: Mapped[int | None] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"))
    position_seconds: Mapped[float | None]
    target_type: Mapped[str | None]
    target_id: Mapped[int | None]
    cause: Mapped[str | None]
    channel: Mapped[str] = mapped_column(default="cable", server_default="cable")
    interrupted_at: Mapped[datetime] = mapped_column(default=utcnow)


class ScheduledLaunch(Base):
    """Dernier lancement programmé d'un canal de diffusion (une ligne par canal)."""
    __tablename__ = "scheduled_launches"

    channel: Mapped[str] = mapped_column(primary_key=True)
    target_type: Mapped[str]
    target_id: Mapped[int]
    started_at: Mapped[datetime]
    active: Mapped[bool] = mapped_column(default=True)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[str]


class ActivityLog(Base):
    __tablename__ = "activity_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(default=utcnow)
    event_type: Mapped[str]
    detail: Mapped[str | None]


class CourseRating(Base):
    """Évaluation 5 étoiles d'un cours vidéo."""
    __tablename__ = "course_ratings"

    id: Mapped[int] = mapped_column(primary_key=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"))
    rating: Mapped[int] = mapped_column()
    channel: Mapped[str] = mapped_column()
    source: Mapped[str] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    video: Mapped["Video"] = relationship(back_populates="ratings")


class PlaybackSession(Base):
    """Session de lecture et assiduité d'un cours vidéo."""
    __tablename__ = "playback_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"))
    channel: Mapped[str] = mapped_column()
    started_at: Mapped[datetime] = mapped_column(default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(nullable=True)
    duration_played_seconds: Mapped[float] = mapped_column(default=0.0)
    total_duration_seconds: Mapped[float] = mapped_column(default=0.0)
    completed: Mapped[bool] = mapped_column(default=False)
    launch_type: Mapped[str] = mapped_column()

    video: Mapped["Video"] = relationship(back_populates="playback_sessions")


class SystemMetricsHistory(Base):
    """Enregistrement périodique (1 min) de la télémétrie matérielle et système."""
    __tablename__ = "system_metrics_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(default=utcnow, index=True)
    cpu_percent: Mapped[float | None] = mapped_column(nullable=True)
    cpu_temp_c: Mapped[float | None] = mapped_column(nullable=True)
    gpu_percent: Mapped[float | None] = mapped_column(nullable=True)
    gpu_temp_c: Mapped[float | None] = mapped_column(nullable=True)
    memory_percent: Mapped[float | None] = mapped_column(nullable=True)
    memory_used_bytes: Mapped[int | None] = mapped_column(nullable=True)
    storage_used_percent: Mapped[float | None] = mapped_column(nullable=True)
    storage_free_bytes: Mapped[int | None] = mapped_column(nullable=True)
    power_watts: Mapped[float | None] = mapped_column(nullable=True)
    extra_data: Mapped[str | None] = mapped_column(Text, nullable=True)

    def get_metric(self, name: str) -> float | None:
        """Extrait dynamiquement la valeur d'une métrique demandée."""
        alias_map = {
            "cpu": "cpu_percent",
            "cpu_temp": "cpu_temp_c",
            "gpu": "gpu_percent",
            "gpu_temp": "gpu_temp_c",
            "memory": "memory_percent",
            "storage": "storage_used_percent",
            "power": "power_watts",
        }
        target_attr = alias_map.get(name, name)
        if hasattr(self, target_attr):
            val = getattr(self, target_attr)
            if val is not None:
                try:
                    return float(val)
                except (ValueError, TypeError):
                    pass

        if self.extra_data:
            try:
                import json
                payload = json.loads(self.extra_data)
                if isinstance(payload, dict):
                    val = payload.get(name) or payload.get(target_attr)
                    if val is not None:
                        return float(val)
            except Exception as exc:
                logger.debug("get_metric : %s", exc)
        return None
