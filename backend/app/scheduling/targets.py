"""Planning d'une cible supprimée (vidéo, playlist, playlist radio)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import OverrideAction, Schedule, ScheduledLaunch, ScheduleOverride, ScheduleTargetType
from app.scheduling.jobs import remove_schedule_job


def drop_schedules_targeting(db: Session, target_type: ScheduleTargetType, target_ids: list[int]) -> list[int]:
    """Retire du planning ce qui vise des cibles supprimées, sans valider la transaction."""
    if not target_ids:
        return []
    schedules = db.query(Schedule).filter(Schedule.target_type == target_type, Schedule.target_id.in_(target_ids)).all()
    removed = [schedule.id for schedule in schedules]
    for schedule in schedules:
        db.delete(schedule)
    db.query(ScheduleOverride).filter(
        ScheduleOverride.action == OverrideAction.replaced,
        ScheduleOverride.replacement_target_type == target_type,
        ScheduleOverride.replacement_target_id.in_(target_ids),
    ).update(
        {
            ScheduleOverride.action: OverrideAction.cancelled,
            ScheduleOverride.replacement_target_type: None,
            ScheduleOverride.replacement_target_id: None,
        },
        synchronize_session=False,
    )
    db.query(ScheduledLaunch).filter(
        ScheduledLaunch.target_type == target_type.value, ScheduledLaunch.target_id.in_(target_ids)
    ).update({ScheduledLaunch.active: False}, synchronize_session=False)
    return removed


def remove_jobs(schedule_ids: list[int]) -> None:
    """Retire les tâches du planificateur des programmations supprimées (après validation de la base)."""
    for schedule_id in schedule_ids:
        remove_schedule_job(schedule_id)
