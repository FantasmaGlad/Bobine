"""API des exceptions d'occurrence d'une programmation récurrente."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.responses import Message
from app.database import get_db
from app.models import (
    OverrideAction,
    Schedule,
    ScheduleOverride,
    ScheduleType,
)
from app.scheduling.occurrences import resolve_target_title
from app.utils.activity_log import log_activity

from .schemas import OverrideInput, OverrideResponse
from .validation import check_target_exists

router = APIRouter()


def _checked_override(db: Session, schedule_id: int, data: OverrideInput) -> datetime:
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
        check_target_exists(db, data.replacement_target_type, data.replacement_target_id)
    return occurrence_date


def _drop_override(db: Session, schedule_id: int, occurrence_date: datetime) -> None:
    existing = (
        db.query(ScheduleOverride)
        .filter(ScheduleOverride.schedule_id == schedule_id, ScheduleOverride.occurrence_date == occurrence_date)
        .first()
    )
    if existing:
        db.delete(existing)
        db.flush()


@router.post("/{schedule_id}/overrides", response_model=OverrideResponse)
def create_override(schedule_id: int, data: OverrideInput, db: Session = Depends(get_db)):
    occurrence_date = _checked_override(db, schedule_id, data)
    _drop_override(db, schedule_id, occurrence_date)
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


@router.delete("/{schedule_id}/overrides/{override_id}", response_model=Message)
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
