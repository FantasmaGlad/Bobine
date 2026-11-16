"""Planning et exceptions."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, OverrideAction, ScheduleTargetType, ScheduleType, UidMixin


class Schedule(UidMixin, Base):
    __uid_prefix__ = "sch"
    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(primary_key=True)
    target_type: Mapped[ScheduleTargetType]
    target_id: Mapped[int]
    schedule_type: Mapped[ScheduleType]
    recurrence_rule: Mapped[str | None]
    run_at: Mapped[datetime | None]
    active: Mapped[bool] = mapped_column(default=True)
    channel: Mapped[str] = mapped_column(default="cable", server_default="cable")

    overrides: Mapped[list["ScheduleOverride"]] = relationship(
        back_populates="schedule", cascade="all, delete-orphan", passive_deletes=True
    )


class ScheduleOverride(UidMixin, Base):
    __uid_prefix__ = "ovr"
    __tablename__ = "schedule_overrides"

    id: Mapped[int] = mapped_column(primary_key=True)
    schedule_id: Mapped[int] = mapped_column(ForeignKey("schedules.id", ondelete="CASCADE"))
    occurrence_date: Mapped[datetime]
    action: Mapped[OverrideAction]
    replacement_target_type: Mapped[ScheduleTargetType | None]
    replacement_target_id: Mapped[int | None]

    schedule: Mapped[Schedule] = relationship(back_populates="overrides")
