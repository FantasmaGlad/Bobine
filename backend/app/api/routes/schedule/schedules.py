"""API du planning : programmations, occurrences et prochaine diffusion."""

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.paging import Window, window
from app.api.responses import Message, NextSchedule
from app.database import get_db
from app.models import (
    OverrideAction,
    Schedule,
)
from app.scheduling.jobs import remove_schedule_job, sync_schedule_job
from app.scheduling.occurrences import ensure_utc, expand_occurrences, resolve_target_title
from app.utils.activity_log import log_activity

from .schemas import OccurrenceResponse, ScheduleInput, ScheduleResponse
from .validation import check_target_exists, normalize_channel, storage_channel, to_response, validate_and_normalize

MAX_OCCURRENCE_SPAN = timedelta(days=62)

router = APIRouter()


@router.get("", response_model=List[ScheduleResponse])
def list_schedules(channel: str | None = None, db: Session = Depends(get_db), page: Window = Depends(window)):
    """Liste des programmations, filtrable par canal de diffusion."""
    query = db.query(Schedule)
    if normalize_channel(channel):
        query = query.filter(Schedule.channel == normalize_channel(channel))
    return [to_response(db, s) for s in page.rows(query.order_by(Schedule.id.desc()))]


@router.get("/occurrences", response_model=List[OccurrenceResponse])
def list_occurrences(start: datetime, end: datetime, channel: str | None = None, db: Session = Depends(get_db),
                     page: Window = Depends(window)):
    """Occurrences résolues (récurrence + overrides) dans [start, end], pour les vues planning calendrier/liste."""
    start, end = ensure_utc(start), ensure_utc(end)
    if end <= start:
        raise HTTPException(status_code=422, detail="La date de fin doit être postérieure à la date de début")
    if end - start > MAX_OCCURRENCE_SPAN:
        raise HTTPException(status_code=422, detail="L'intervalle demandé dépasse 62 jours")
    query = db.query(Schedule).filter(Schedule.active == True)  # noqa: E712
    if normalize_channel(channel):
        query = query.filter(Schedule.channel == normalize_channel(channel))
    return page.items(expand_occurrences(db, query.all(), start, end))


@router.get("/next", response_model=Optional[NextSchedule])
def get_next_schedule(channel: str | None = None, db: Session = Depends(get_db)):
    """Prochaine occurrence active à venir, récurrence et overrides résolus, pour le bloc « prochain cours » de l'écran d'attente."""
    now = datetime.now(timezone.utc)
    horizon = now + timedelta(days=60)
    query = db.query(Schedule).filter(Schedule.active == True)  # noqa: E712
    if normalize_channel(channel):
        query = query.filter(Schedule.channel == normalize_channel(channel))
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
    return to_response(db, schedule)


@router.post("", response_model=ScheduleResponse)
async def create_schedule(data: ScheduleInput, db: Session = Depends(get_db)):
    check_target_exists(db, data.target_type, data.target_id)
    run_at, recurrence_rule = validate_and_normalize(data)

    schedule = Schedule(
        target_type=data.target_type,
        target_id=data.target_id,
        schedule_type=data.schedule_type,
        run_at=run_at,
        recurrence_rule=recurrence_rule,
        active=data.active,
        channel=storage_channel(data.channel, data.target_type),
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    sync_schedule_job(schedule)
    title, _ = resolve_target_title(db, schedule.target_type, schedule.target_id)
    log_activity(db, "schedule_created", f"{title or schedule.target_type.value} ({schedule.schedule_type.value})")
    return to_response(db, schedule)


@router.put("/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(schedule_id: int, data: ScheduleInput, db: Session = Depends(get_db)):
    schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Programmation non trouvée")
    check_target_exists(db, data.target_type, data.target_id)
    run_at, recurrence_rule = validate_and_normalize(data)

    schedule.target_type = data.target_type
    schedule.target_id = data.target_id
    schedule.schedule_type = data.schedule_type
    schedule.run_at = run_at
    schedule.recurrence_rule = recurrence_rule
    schedule.active = data.active
    schedule.channel = storage_channel(data.channel, data.target_type)
    db.commit()
    db.refresh(schedule)
    sync_schedule_job(schedule)
    title, _ = resolve_target_title(db, schedule.target_type, schedule.target_id)
    log_activity(db, "schedule_updated", title or schedule.target_type.value)
    return to_response(db, schedule)


@router.delete("/{schedule_id}", response_model=Message)
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
