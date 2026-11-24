"""Validation d'une programmation : canal, cible, horaires, et sa vue publique."""

import json
import re
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.contract import DEFAULT_CHANNEL, SCHEDULE_CHANNELS
from app.models import (
    Playlist,
    RadioPlaylist,
    Schedule,
    ScheduleTargetType,
    ScheduleType,
    Video,
)
from app.scheduling.occurrences import ensure_utc, resolve_target_display

from .schemas import ScheduleInput

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


_CHANNELS = SCHEDULE_CHANNELS


def normalize_channel(value: str | None) -> str | None:
    """Sortie d'une programmation ; lève 422 si une valeur fournie ne désigne pas une sortie."""
    if value is None:
        return None
    if value in _CHANNELS:
        return value
    expected = ", ".join(f"'{channel}'" for channel in _CHANNELS)
    raise HTTPException(status_code=422, detail=f"Sortie invalide (attendu {expected})")


def storage_channel(value: str | None) -> str:
    return normalize_channel(value) or DEFAULT_CHANNEL


def check_target_exists(db: Session, target_type: ScheduleTargetType, target_id: int) -> None:
    if target_type == ScheduleTargetType.video:
        found = db.query(Video).filter(Video.id == target_id).first()
    elif target_type == ScheduleTargetType.radio_playlist:
        found = db.query(RadioPlaylist).filter(RadioPlaylist.id == target_id).first()
    else:
        found = db.query(Playlist).filter(Playlist.id == target_id).first()
    if not found:
        raise HTTPException(status_code=404, detail=f"Cible introuvable ({target_type.value} {target_id})")


def validate_and_normalize(data: ScheduleInput) -> tuple[datetime | None, str | None]:
    if data.schedule_type == ScheduleType.once:
        if data.run_at is None:
            raise HTTPException(status_code=422, detail="Une programmation ponctuelle nécessite une date/heure")
        run_at = ensure_utc(data.run_at)
        if run_at <= datetime.now(timezone.utc):
            raise HTTPException(status_code=422, detail="Une programmation ponctuelle doit être dans le futur")
        return run_at, None

    if not data.days_of_week:
        raise HTTPException(
            status_code=422, detail="Une programmation récurrente nécessite au moins un jour de la semaine"
        )
    if any(d < 0 or d > 6 for d in data.days_of_week):
        raise HTTPException(status_code=422, detail="Jour de semaine invalide (attendu 0=lundi à 6=dimanche)")
    if not data.time_of_day or not _TIME_RE.match(data.time_of_day):
        raise HTTPException(status_code=422, detail="Heure invalide (attendu HH:MM)")

    rule_dict: dict = {"days_of_week": sorted(set(data.days_of_week)), "time": data.time_of_day}

    if data.target_type == ScheduleTargetType.radio_playlist:
        if data.is_24_7:
            rule_dict["mode"] = "24_7"
        elif data.end_time:
            if not _TIME_RE.match(data.end_time):
                raise HTTPException(status_code=422, detail="Heure de fin invalide (attendu HH:MM)")
            if data.end_time <= data.time_of_day:
                raise HTTPException(
                    status_code=422,
                    detail="L'heure de fin doit être après l'heure de début "
                    "(fenêtres à cheval sur minuit non prises en charge)",
                )
            rule_dict["end_time"] = data.end_time

    return None, json.dumps(rule_dict)


def to_response(db: Session, schedule: Schedule) -> dict:
    display = resolve_target_display(db, schedule.target_type, schedule.target_id)
    days_of_week, time_of_day, end_time, is_24_7 = None, None, None, False
    if schedule.recurrence_rule:
        rule = json.loads(schedule.recurrence_rule)
        days_of_week = rule.get("days_of_week")
        time_of_day = rule.get("time")
        end_time = rule.get("end_time")
        is_24_7 = rule.get("mode") == "24_7"
    return {
        "id": schedule.id,
        "channel": schedule.channel or DEFAULT_CHANNEL,
        "target_type": schedule.target_type,
        "target_id": schedule.target_id,
        "target_title": display["title"],
        "target_program": display["program"],
        "target_duration_seconds": display["duration_seconds"],
        "target_thumbnail_path": display["thumbnail_path"],
        "target_cover_track_id": display["cover_track_id"],
        "schedule_type": schedule.schedule_type,
        "run_at": ensure_utc(schedule.run_at) if schedule.run_at else None,
        "days_of_week": days_of_week,
        "time_of_day": time_of_day,
        "active": schedule.active,
        "override_count": len(schedule.overrides),
        "end_time": end_time,
        "is_24_7": is_24_7,
    }
