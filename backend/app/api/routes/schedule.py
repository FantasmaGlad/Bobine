import json
import re
from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.contract import CHANNELS, DEFAULT_CHANNEL, SCHEDULE_CHANNELS
from app.database import get_db
from app.models import (
    OverrideAction,
    Playlist,
    RadioPlaylist,
    Schedule,
    ScheduleOverride,
    ScheduleTargetType,
    ScheduleType,
    Video,
)
from app.radio_manager import LEGACY_RADIO_CHANNEL, RADIO_CHANNELS, normalize_radio_channel
from app.scheduling.jobs import remove_schedule_job, sync_schedule_job
from app.scheduling.occurrences import ensure_utc, expand_occurrences, resolve_target_display, resolve_target_title
from app.utils.activity_log import log_activity

router = APIRouter(prefix="/api/schedule", tags=["schedule"])

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
_CHANNELS = SCHEDULE_CHANNELS


def _normalize_channel(value: str | None) -> str | None:
    if value == LEGACY_RADIO_CHANNEL:
        return normalize_radio_channel(value)
    return value if value in _CHANNELS else None


def _storage_channel(value: str | None, target_type: ScheduleTargetType) -> str:
    channel = _normalize_channel(value)
    if target_type == ScheduleTargetType.radio_playlist:
        return channel if channel in RADIO_CHANNELS else normalize_radio_channel(None)
    return channel if channel in CHANNELS else DEFAULT_CHANNEL


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


def _check_target_exists(db: Session, target_type: ScheduleTargetType, target_id: int) -> None:
    if target_type == ScheduleTargetType.video:
        found = db.query(Video).filter(Video.id == target_id).first()
    elif target_type == ScheduleTargetType.radio_playlist:
        found = db.query(RadioPlaylist).filter(RadioPlaylist.id == target_id).first()
    else:
        found = db.query(Playlist).filter(Playlist.id == target_id).first()
    if not found:
        raise HTTPException(status_code=404, detail=f"Cible introuvable ({target_type.value} {target_id})")


def _validate_and_normalize(data: ScheduleInput) -> tuple[datetime | None, str | None]:
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


def _to_response(db: Session, schedule: Schedule) -> dict:
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


@router.get("", response_model=List[ScheduleResponse])
def list_schedules(channel: str | None = None, db: Session = Depends(get_db)):
    """Liste des programmations, filtrable par canal de diffusion."""
    query = db.query(Schedule)
    if _normalize_channel(channel):
        query = query.filter(Schedule.channel == _normalize_channel(channel))
    return [_to_response(db, s) for s in query.order_by(Schedule.id.desc()).all()]


@router.get("/occurrences", response_model=List[OccurrenceResponse])
def list_occurrences(start: datetime, end: datetime, channel: str | None = None, db: Session = Depends(get_db)):
    """Occurrences résolues (récurrence + overrides) dans [start, end], pour les vues planning calendrier/liste."""
    start, end = ensure_utc(start), ensure_utc(end)
    if end <= start:
        raise HTTPException(status_code=422, detail="La date de fin doit être postérieure à la date de début")
    query = db.query(Schedule).filter(Schedule.active == True)  # noqa: E712
    if _normalize_channel(channel):
        query = query.filter(Schedule.channel == _normalize_channel(channel))
    return expand_occurrences(db, query.all(), start, end)


@router.get("/next")
def get_next_schedule(channel: str | None = None, db: Session = Depends(get_db)):
    """Prochaine occurrence active à venir, récurrence et overrides résolus, pour le bloc « prochain cours » de l'écran d'attente."""
    now = datetime.now(timezone.utc)
    horizon = now + timedelta(days=60)
    query = db.query(Schedule).filter(Schedule.active == True)  # noqa: E712
    if _normalize_channel(channel):
        query = query.filter(Schedule.channel == _normalize_channel(channel))
    schedules = query.all()
    occurrences = expand_occurrences(db, schedules, now, horizon)
    upcoming = next((o for o in occurrences if o["override_action"] != OverrideAction.cancelled), None)
    if not upcoming:
        return None
    return {"run_at": upcoming["run_at"].isoformat(), "title": upcoming["title"]}


@router.get("/{schedule_id}", response_model=ScheduleResponse)
def get_schedule(schedule_id: int, db: Session = Depends(get_db)):
    schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Programmation non trouvée")
    return _to_response(db, schedule)


@router.post("", response_model=ScheduleResponse)
async def create_schedule(data: ScheduleInput, db: Session = Depends(get_db)):
    _check_target_exists(db, data.target_type, data.target_id)
    run_at, recurrence_rule = _validate_and_normalize(data)

    schedule = Schedule(
        target_type=data.target_type,
        target_id=data.target_id,
        schedule_type=data.schedule_type,
        run_at=run_at,
        recurrence_rule=recurrence_rule,
        active=data.active,
        channel=_storage_channel(data.channel, data.target_type),
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    sync_schedule_job(schedule)
    title, _ = resolve_target_title(db, schedule.target_type, schedule.target_id)
    log_activity(db, "schedule_created", f"{title or schedule.target_type.value} ({schedule.schedule_type.value})")
    return _to_response(db, schedule)


@router.put("/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(schedule_id: int, data: ScheduleInput, db: Session = Depends(get_db)):
    schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Programmation non trouvée")
    _check_target_exists(db, data.target_type, data.target_id)
    run_at, recurrence_rule = _validate_and_normalize(data)

    schedule.target_type = data.target_type
    schedule.target_id = data.target_id
    schedule.schedule_type = data.schedule_type
    schedule.run_at = run_at
    schedule.recurrence_rule = recurrence_rule
    schedule.active = data.active
    schedule.channel = _storage_channel(data.channel, data.target_type)
    db.commit()
    db.refresh(schedule)
    sync_schedule_job(schedule)
    title, _ = resolve_target_title(db, schedule.target_type, schedule.target_id)
    log_activity(db, "schedule_updated", title or schedule.target_type.value)
    return _to_response(db, schedule)


@router.delete("/{schedule_id}")
async def delete_schedule(schedule_id: int, db: Session = Depends(get_db)):
    schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Programmation non trouvée")
    title, _ = resolve_target_title(db, schedule.target_type, schedule.target_id)
    db.delete(schedule)
    db.commit()
    remove_schedule_job(schedule_id)
    log_activity(db, "schedule_deleted", title or schedule.target_type.value)
    return {"message": "Programmation supprimée avec succès"}


@router.post("/{schedule_id}/overrides", response_model=OverrideResponse)
def create_override(schedule_id: int, data: OverrideInput, db: Session = Depends(get_db)):
    schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Programmation non trouvée")
    if schedule.schedule_type != ScheduleType.recurring:
        raise HTTPException(status_code=409, detail="Les overrides ne s'appliquent qu'aux programmations récurrentes")

    try:
        occurrence_date = datetime.strptime(data.occurrence_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=422, detail="Date d'occurrence invalide (attendu YYYY-MM-DD)")

    if data.action == OverrideAction.replaced:
        if not data.replacement_target_type or not data.replacement_target_id:
            raise HTTPException(status_code=422, detail="Une occurrence remplacée nécessite une cible de remplacement")
        _check_target_exists(db, data.replacement_target_type, data.replacement_target_id)

    existing = (
        db.query(ScheduleOverride)
        .filter(ScheduleOverride.schedule_id == schedule_id, ScheduleOverride.occurrence_date == occurrence_date)
        .first()
    )
    if existing:
        db.delete(existing)
        db.flush()

    override = ScheduleOverride(
        schedule_id=schedule_id,
        occurrence_date=occurrence_date,
        action=data.action,
        replacement_target_type=data.replacement_target_type if data.action == OverrideAction.replaced else None,
        replacement_target_id=data.replacement_target_id if data.action == OverrideAction.replaced else None,
    )
    db.add(override)
    db.commit()
    db.refresh(override)

    title = None
    if override.action == OverrideAction.replaced:
        title, _ = resolve_target_title(db, override.replacement_target_type, override.replacement_target_id)

    log_activity(
        db, "schedule_override_created",
        f"{data.occurrence_date} — {override.action.value}" + (f" par {title}" if title else ""),
    )

    return {
        "id": override.id,
        "occurrence_date": data.occurrence_date,
        "action": override.action,
        "replacement_target_type": override.replacement_target_type,
        "replacement_target_id": override.replacement_target_id,
        "replacement_title": title,
    }


@router.delete("/{schedule_id}/overrides/{override_id}")
def delete_override(schedule_id: int, override_id: int, db: Session = Depends(get_db)):
    override = (
        db.query(ScheduleOverride)
        .filter(ScheduleOverride.id == override_id, ScheduleOverride.schedule_id == schedule_id)
        .first()
    )
    if not override:
        raise HTTPException(status_code=404, detail="Override non trouvé")
    db.delete(override)
    db.commit()
    return {"message": "Override supprimé, l'occurrence redevient normale"}
