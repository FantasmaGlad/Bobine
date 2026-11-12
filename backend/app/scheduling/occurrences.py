"""Occurrences du planning : récurrences développées, annulations et remplacements résolus (aucun effet de bord)."""

import json
from datetime import date, datetime, timezone

from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session
from tzlocal import get_localzone

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

LOCAL_TZ = get_localzone()

_MAX_OCCURRENCES_PER_SCHEDULE = 1000


def ensure_utc(value: datetime) -> datetime:
    """SQLite ne conserve pas le fuseau des datetimes stockés : une valeur aware écrite en base est relue *naïve* par SQLAlchemy, alors qu'elle représente toujours un instant UTC (convention utilisée dans tout le schéma — imported_at, created_at, etc.)."""
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _build_cron_trigger(schedule: Schedule) -> CronTrigger:
    rule = json.loads(schedule.recurrence_rule)
    days = ",".join(str(d) for d in rule["days_of_week"])
    hour, minute = (int(part) for part in rule["time"].split(":"))
    return CronTrigger(day_of_week=days, hour=hour, minute=minute, timezone=LOCAL_TZ)


def resolve_target_title(
    db: Session, target_type: ScheduleTargetType, target_id: int
) -> tuple[str | None, str | None]:
    """Titre + programme d'une cible de programmation, pour l'affichage (planning, overrides)."""
    if target_type == ScheduleTargetType.video:
        video = db.query(Video).filter(Video.id == target_id).first()
        return (video.title, video.program) if video else (None, None)
    if target_type == ScheduleTargetType.radio_playlist:
        radio_playlist = db.query(RadioPlaylist).filter(RadioPlaylist.id == target_id).first()
        return (radio_playlist.name, None) if radio_playlist else (None, None)
    playlist = db.query(Playlist).filter(Playlist.id == target_id).first()
    return (playlist.name, None) if playlist else (None, None)


def resolve_target_display(db: Session, target_type: ScheduleTargetType, target_id: int) -> dict:
    """Titre/programme/durée/miniature d'une cible de programmation, pour le planning visuel."""
    if target_type == ScheduleTargetType.video:
        video = db.query(Video).filter(Video.id == target_id).first()
        if not video:
            return {"title": None, "program": None, "duration_seconds": None, "thumbnail_path": None, "cover_track_id": None}
        return {
            "title": video.title,
            "program": video.program,
            "duration_seconds": video.duration_seconds,
            "thumbnail_path": video.thumbnail_path,
            "cover_track_id": None,
        }
    if target_type == ScheduleTargetType.radio_playlist:
        radio_playlist = db.query(RadioPlaylist).filter(RadioPlaylist.id == target_id).first()
        if not radio_playlist:
            return {"title": None, "program": None, "duration_seconds": None, "thumbnail_path": None, "cover_track_id": None}
        items = sorted(radio_playlist.items, key=lambda it: it.position)
        cover_track_id = next((it.track.id for it in items if it.track and it.track.cover_path), None)
        return {
            "title": radio_playlist.name,
            "program": None,
            "duration_seconds": None,
            "thumbnail_path": None,
            "cover_track_id": cover_track_id,
        }
    playlist = db.query(Playlist).filter(Playlist.id == target_id).first()
    if not playlist:
        return {"title": None, "program": None, "duration_seconds": None, "thumbnail_path": None, "cover_track_id": None}
    items = sorted(playlist.items, key=lambda it: it.position)
    first_thumbnail = next((it.video.thumbnail_path for it in items if it.video and it.video.thumbnail_path), None)
    total_duration = sum((it.video.duration_seconds or 0.0) for it in items if it.video)
    return {
        "title": playlist.name,
        "program": None,
        "duration_seconds": total_duration,
        "thumbnail_path": first_thumbnail,
        "cover_track_id": None,
    }


def expand_occurrences(
    db: Session, schedules: list[Schedule], start: datetime, end: datetime
) -> list[dict]:
    """Développe une liste de programmations actives en occurrences concrètes dans l'intervalle [start, end], overrides résolus."""
    if not schedules:
        return []

    schedule_ids = [s.id for s in schedules]
    overrides = (
        db.query(ScheduleOverride).filter(ScheduleOverride.schedule_id.in_(schedule_ids)).all()
    )
    overrides_by_key: dict[tuple[int, date], ScheduleOverride] = {
        (o.schedule_id, o.occurrence_date.date()): o for o in overrides
    }

    results: list[dict] = []
    for schedule in schedules:
        window_end_time, window_is_24_7 = None, False
        if schedule.recurrence_rule:
            rule = json.loads(schedule.recurrence_rule)
            window_end_time = rule.get("end_time")
            window_is_24_7 = rule.get("mode") == "24_7"

        if schedule.schedule_type == ScheduleType.once:
            run_at = ensure_utc(schedule.run_at) if schedule.run_at else None
            if run_at and start <= run_at <= end:
                display = resolve_target_display(db, schedule.target_type, schedule.target_id)
                results.append(
                    {
                        "schedule_id": schedule.id,
                        "channel": schedule.channel or "cable",
                        "schedule_type": schedule.schedule_type,
                        "run_at": run_at,
                        "target_type": schedule.target_type,
                        "target_id": schedule.target_id,
                        "title": display["title"],
                        "program": display["program"],
                        "duration_seconds": display["duration_seconds"],
                        "thumbnail_path": display["thumbnail_path"],
                        "cover_track_id": display["cover_track_id"],
                        "end_time": window_end_time,
                        "is_24_7": window_is_24_7,
                        "is_override": False,
                        "override_action": None,
                        "override_id": None,
                    }
                )
            continue

        trigger = _build_cron_trigger(schedule)
        fire_time = trigger.get_next_fire_time(None, start)
        guard = 0
        while fire_time is not None and fire_time <= end and guard < _MAX_OCCURRENCES_PER_SCHEDULE:
            guard += 1
            override = overrides_by_key.get((schedule.id, fire_time.date()))

            if override is not None and override.action == OverrideAction.cancelled:
                display = resolve_target_display(db, schedule.target_type, schedule.target_id)
                results.append(
                    {
                        "schedule_id": schedule.id,
                        "channel": schedule.channel or "cable",
                        "schedule_type": schedule.schedule_type,
                        "run_at": fire_time,
                        "target_type": schedule.target_type,
                        "target_id": schedule.target_id,
                        "title": display["title"],
                        "program": display["program"],
                        "duration_seconds": display["duration_seconds"],
                        "thumbnail_path": display["thumbnail_path"],
                        "cover_track_id": display["cover_track_id"],
                        "end_time": window_end_time,
                        "is_24_7": window_is_24_7,
                        "is_override": True,
                        "override_action": OverrideAction.cancelled,
                        "override_id": override.id,
                    }
                )
            elif override is not None and override.action == OverrideAction.replaced:
                display = resolve_target_display(
                    db, override.replacement_target_type, override.replacement_target_id
                )
                results.append(
                    {
                        "schedule_id": schedule.id,
                        "channel": schedule.channel or "cable",
                        "schedule_type": schedule.schedule_type,
                        "run_at": fire_time,
                        "target_type": override.replacement_target_type,
                        "target_id": override.replacement_target_id,
                        "title": display["title"],
                        "program": display["program"],
                        "duration_seconds": display["duration_seconds"],
                        "thumbnail_path": display["thumbnail_path"],
                        "cover_track_id": display["cover_track_id"],
                        "end_time": window_end_time,
                        "is_24_7": window_is_24_7,
                        "is_override": True,
                        "override_action": OverrideAction.replaced,
                        "override_id": override.id,
                    }
                )
            else:
                display = resolve_target_display(db, schedule.target_type, schedule.target_id)
                results.append(
                    {
                        "schedule_id": schedule.id,
                        "channel": schedule.channel or "cable",
                        "schedule_type": schedule.schedule_type,
                        "run_at": fire_time,
                        "target_type": schedule.target_type,
                        "target_id": schedule.target_id,
                        "title": display["title"],
                        "program": display["program"],
                        "duration_seconds": display["duration_seconds"],
                        "thumbnail_path": display["thumbnail_path"],
                        "cover_track_id": display["cover_track_id"],
                        "end_time": window_end_time,
                        "is_24_7": window_is_24_7,
                        "is_override": False,
                        "override_action": None,
                        "override_id": None,
                    }
                )

            fire_time = trigger.get_next_fire_time(fire_time, fire_time)

    results.sort(key=lambda o: o["run_at"])
    return results
