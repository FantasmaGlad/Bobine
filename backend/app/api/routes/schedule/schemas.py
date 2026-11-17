"""Schémas de l'API du planning."""

from datetime import datetime
from typing import List

from pydantic import BaseModel

from app.api.contract import DEFAULT_CHANNEL
from app.models import (
    OverrideAction,
    ScheduleTargetType,
    ScheduleType,
)


class ScheduleInput(BaseModel):
    target_type: ScheduleTargetType
    target_id: int
    channel: str = DEFAULT_CHANNEL
    schedule_type: ScheduleType
    run_at: datetime | None = None
    days_of_week: List[int] | None = None
    time_of_day: str | None = None
    active: bool = True
    end_time: str | None = None
    is_24_7: bool = False


class ScheduleResponse(BaseModel):
    id: int
    channel: str
    target_type: ScheduleTargetType
    target_id: int
    target_title: str | None
    target_program: str | None
    target_duration_seconds: float | None = None
    target_thumbnail_path: str | None = None
    target_cover_track_id: int | None = None
    schedule_type: ScheduleType
    run_at: datetime | None
    days_of_week: List[int] | None
    time_of_day: str | None
    active: bool
    override_count: int
    end_time: str | None = None
    is_24_7: bool = False


class OverrideInput(BaseModel):
    occurrence_date: str
    action: OverrideAction
    replacement_target_type: ScheduleTargetType | None = None
    replacement_target_id: int | None = None


class OverrideResponse(BaseModel):
    id: int
    occurrence_date: str
    action: OverrideAction
    replacement_target_type: ScheduleTargetType | None
    replacement_target_id: int | None
    replacement_title: str | None


class OccurrenceResponse(BaseModel):
    schedule_id: int
    channel: str
    schedule_type: ScheduleType
    run_at: datetime
    target_type: ScheduleTargetType
    target_id: int
    title: str | None
    program: str | None
    duration_seconds: float | None = None
    thumbnail_path: str | None = None
    cover_track_id: int | None = None
    end_time: str | None = None
    is_24_7: bool = False
    is_override: bool
    override_action: OverrideAction | None
    override_id: int | None
