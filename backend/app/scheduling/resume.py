"""Reprise des programmations en cours au démarrage du serveur."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.api.contract import CHANNELS
from app.database import SessionLocal
from app.models import OverrideAction, Schedule, ScheduleTargetType
from app.playback.constants import PlaybackStateEnum
from app.playback.manager import get_playback_manager
from app.scheduling.launch import launch_target, scheduled_target_unavailable
from app.scheduling.occurrences import ensure_utc, expand_occurrences
from app.scheduling import launch_store as scheduled_launch_store

logger = logging.getLogger(__name__)

LOOKBACK = timedelta(hours=12)
SAME_LAUNCH_TOLERANCE = timedelta(minutes=2)
RETRY_DELAYS_SECONDS = (10.0, 20.0, 30.0)
PLAYABLE_TARGETS = (ScheduleTargetType.video, ScheduleTargetType.playlist)

_retry_task: asyncio.Task | None = None


@dataclass(frozen=True)
class ResumeCandidate:
    channel: str
    target_type: ScheduleTargetType
    target_id: int
    started_at: datetime


def _last_occurrence(db: Session, channel: str, now: datetime) -> ResumeCandidate | None:
    schedules = db.query(Schedule).filter(Schedule.active.is_(True)).all()
    started = [
        o for o in expand_occurrences(db, schedules, now - LOOKBACK, now)
        if o["channel"] == channel and o["override_action"] != OverrideAction.cancelled and o["target_type"] in PLAYABLE_TARGETS
    ]
    if not started:
        return None
    last = max(started, key=lambda o: o["run_at"])
    return ResumeCandidate(channel, last["target_type"], last["target_id"], ensure_utc(last["run_at"]))


def choose_candidate(db: Session, channel: str, now: datetime) -> ResumeCandidate | None:
    """Ce qu'il faut relancer sur `channel`, ou `None`."""
    record = scheduled_launch_store.get(db, channel)
    recorded_at = ensure_utc(record.started_at) if record else None
    occurrence = _last_occurrence(db, channel, now)
    if occurrence and (recorded_at is None or occurrence.started_at > recorded_at + SAME_LAUNCH_TOLERANCE):
        return occurrence
    if record and record.active and now - recorded_at <= LOOKBACK:
        return ResumeCandidate(channel, ScheduleTargetType(record.target_type), record.target_id, recorded_at)
    return None


async def _resume_channel(channel: str) -> bool:
    with SessionLocal() as db:
        candidate = choose_candidate(db, channel, datetime.now(timezone.utc))
        if candidate is None:
            return True
        if get_playback_manager(channel).snapshot()["state"] != PlaybackStateEnum.waiting.value:
            return True
        if scheduled_target_unavailable(db, candidate.target_type, candidate.target_id):
            return False
        logger.info(
            f"Reprise ({channel}) : {candidate.target_type.value} {candidate.target_id} lancé à "
            f"{candidate.started_at.isoformat()}"
        )
        await launch_target(db, candidate.target_type, candidate.target_id, channel, resumed_from=candidate.started_at)
        return True


async def _resume(channels: tuple[str, ...]) -> tuple[str, ...]:
    pending = []
    for channel in channels:
        try:
            if not await _resume_channel(channel):
                pending.append(channel)
        except Exception:
            logger.exception(f"Reprise ({channel}) impossible")
    return tuple(pending)


async def _retry(pending: tuple[str, ...]) -> None:
    for delay in RETRY_DELAYS_SECONDS:
        await asyncio.sleep(delay)
        pending = await _resume(pending)
        if not pending:
            return
    logger.warning(f"Reprise abandonnée, support externe toujours absent : {', '.join(pending)}")


async def resume_running_schedules() -> None:
    """À appeler une fois au démarrage, après le stockage et le planificateur."""
    global _retry_task
    pending = await _resume(tuple(CHANNELS))
    if pending:
        _retry_task = asyncio.create_task(_retry(pending))


def cancel_pending_resume() -> None:
    if _retry_task is not None and not _retry_task.done():
        _retry_task.cancel()
