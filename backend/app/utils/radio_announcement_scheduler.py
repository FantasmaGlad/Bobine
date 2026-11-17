"""Moteur des règles temporelles de rappels : « toutes les X minutes » et « à heures fixes »."""
import asyncio
import json
import logging
import time
from datetime import datetime

from sqlalchemy import func
from tzlocal import get_localzone

from app.database import SessionLocal
from app.models import RadioAnnouncement, RadioAnnouncementRule, RadioAnnouncementRuleType
from app.radio.channels import rule_targets_output

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 10.0
LOCAL_TZ = get_localzone()

_task: asyncio.Task | None = None
_last_minutes_fire: dict[tuple[int, str], float] = {}
_last_fixed_fire: dict[tuple[int, str], str] = {}


def start_radio_announcement_scheduler() -> None:
    global _task
    if _task is None or _task.done():
        _task = asyncio.create_task(_loop())


async def stop_radio_announcement_scheduler() -> None:
    global _task
    if _task is not None:
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
        _task = None


async def _loop() -> None:
    try:
        while True:
            await asyncio.sleep(CHECK_INTERVAL_SECONDS)
            try:
                await _check_rules()
            except Exception as e:
                logger.error(f"Vérification des règles de rappels échouée : {e}", exc_info=True)
    except asyncio.CancelledError:
        pass


async def _check_rules() -> None:
    from app.radio.manager import get_all_radio_managers

    for manager in get_all_radio_managers().values():
        await _check_rules_for(manager)


def _timed_rules(db, channel: str) -> list[RadioAnnouncementRule]:
    rules = (
        db.query(RadioAnnouncementRule)
        .filter(
            RadioAnnouncementRule.enabled == True,  # noqa: E712
            RadioAnnouncementRule.rule_type.in_(
                [RadioAnnouncementRuleType.every_x_minutes, RadioAnnouncementRuleType.fixed_times]
            ),
        )
        .all()
    )
    return [rule for rule in rules if rule_targets_output(rule.target, channel)]


def _is_due(rule: RadioAnnouncementRule, channel: str, now_monotonic: float, now_local: datetime) -> bool:
    fire_key = (rule.id, channel)
    if rule.rule_type == RadioAnnouncementRuleType.every_x_minutes:
        last = _last_minutes_fire.setdefault(fire_key, now_monotonic)
        if now_monotonic - last >= (rule.interval_minutes or 0) * 60:
            _last_minutes_fire[fire_key] = now_monotonic
            return True
    elif rule.rule_type == RadioAnnouncementRuleType.fixed_times:
        times = json.loads(rule.times_of_day) if rule.times_of_day else []
        hhmm = now_local.strftime("%H:%M")
        minute_key = f"{now_local.date()} {hhmm}"
        if hhmm in times and _last_fixed_fire.get(fire_key) != minute_key:
            _last_fixed_fire[fire_key] = minute_key
            return True
    return False


async def _check_rules_for(manager) -> None:
    if manager.state.get("current_announcement"):
        return
    db = SessionLocal()
    try:
        rules = _timed_rules(db, manager.channel)
        now_monotonic = time.monotonic()
        now_local = datetime.now(LOCAL_TZ)
        if not any(_is_due(rule, manager.channel, now_monotonic, now_local) for rule in rules):
            return
        announcement = (
            db.query(RadioAnnouncement)
            .filter(RadioAnnouncement.enabled == True)  # noqa: E712
            .order_by(func.random())
            .first()
        )
        if not announcement:
            return
        await manager.play_announcement(
            {"id": announcement.id, "description": announcement.description}, mode="duck",
        )
    finally:
        db.close()
