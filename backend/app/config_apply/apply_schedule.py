"""Planning d'un canal et ses remplacements d'occurrence."""
from __future__ import annotations
import json
from datetime import datetime
from sqlalchemy.orm import Session
from app import config_files
from app.utils.uid import is_uid
from app.models import (
    OverrideAction, Playlist, RadioPlaylist, Schedule, ScheduleOverride, ScheduleTargetType, ScheduleType,
)
from app.config_apply.context import _Context, _by_uid
from app.config_apply.resolve import _unique_by_name, _video
from app.config_apply.values import _TIME_RE, _flag, _list


def _resync_all_schedules(channel: str | None):
    async def resync(db: Session) -> None:
        from app.scheduling.jobs import sync_schedule_job

        for schedule in db.query(Schedule).all():
            if channel is None or schedule.channel == channel:
                sync_schedule_job(schedule)

    return resync


def _schedule_target(ctx: _Context, file: str, ref: dict | None) -> tuple[ScheduleTargetType, int] | None:
    kind = (ref or {}).get("type")
    if kind == "video":
        video = _video(ctx, file, (ref or {}).get("video") or {})
        return (ScheduleTargetType.video, video.id) if video else None
    if kind in ("playlist", "radio_playlist"):
        model = Playlist if kind == "playlist" else RadioPlaylist
        playlist = _by_uid(ctx, model, ref) or _unique_by_name(ctx, file, model, (ref or {}).get("name"))
        if playlist is None:
            ctx.fail(file, f"playlist introuvable : {(ref or {}).get('name')!r}")
            return None
        return ScheduleTargetType(kind), playlist.id
    ctx.fail(file, f"cible invalide : {ref!r}")
    return None


def _signature(schedule: Schedule) -> tuple:
    rule = json.dumps(json.loads(schedule.recurrence_rule), sort_keys=True) if schedule.recurrence_rule else None
    return (schedule.target_type, schedule.target_id, schedule.schedule_type, config_files._iso(schedule.run_at), rule)


def _set_timing(ctx: _Context, file: str, entry: dict, wanted: Schedule, radio: bool) -> bool:
    from app.scheduling.occurrences import ensure_utc

    if entry.get("type") == "once":
        try:
            wanted.schedule_type, wanted.run_at = ScheduleType.once, ensure_utc(datetime.fromisoformat(entry["run_at"]))
        except (KeyError, TypeError, ValueError):
            ctx.fail(file, f"run_at (date ISO 8601) requis pour une programmation ponctuelle : {entry!r}")
            return False
        return True
    if entry.get("type") != "recurring":
        ctx.fail(file, f"type de programmation invalide : {entry.get('type')!r}")
        return False
    rule = entry.get("recurrence") or {}
    days, time = rule.get("days_of_week"), rule.get("time")
    if not days or any(not isinstance(d, int) or not 0 <= d <= 6 for d in days) or not isinstance(time, str) or not _TIME_RE.match(time):
        ctx.fail(file, f"recurrence invalide (days_of_week 0 à 6, time HH:MM) : {rule!r}")
        return False
    end = rule.get("end_time")
    if end is not None and (not radio or not _TIME_RE.match(str(end)) or end <= time):
        ctx.fail(file, f"end_time invalide (radio seulement, après time) : {rule!r}")
        return False
    wanted.schedule_type, wanted.recurrence_rule = ScheduleType.recurring, json.dumps(
        {**{k: v for k, v in rule.items() if k in ("end_time", "mode")}, "days_of_week": sorted(set(days)), "time": time})
    return True


def _wanted_schedule(ctx: _Context, file: str, entry: dict, channel: str, radio: bool) -> Schedule | None:
    target = _schedule_target(ctx, file, entry.get("target"))
    if target is None:
        return None
    if (target[0] == ScheduleTargetType.radio_playlist) != radio:
        ctx.fail(file, f"cible {target[0].value} impossible sur le canal {channel}")
        return None
    wanted = Schedule(target_type=target[0], target_id=target[1], channel=channel,
                      active=_flag(ctx, file, "« active » de la programmation", entry.get("active", True)))
    return wanted if _set_timing(ctx, file, entry, wanted, radio) else None


def _entry_overrides(ctx: _Context, file: str, entry: dict) -> list:
    overrides = []
    for override in entry.get("overrides") or []:
        try:
            action = OverrideAction(override["action"])
            date = datetime.fromisoformat(override["date"])
        except (KeyError, TypeError, ValueError):
            ctx.fail(file, f"exception de planning invalide : {override!r}")
            continue
        replacement = _schedule_target(ctx, file, override.get("replacement")) if action == OverrideAction.replaced else None
        overrides.append((override.get("uid"), date, action, replacement))
    return overrides


def _place_schedule(ctx: _Context, entry: dict, wanted: Schedule, by_uid: dict, unused: list, kept: list) -> Schedule:
    uid = entry.get("uid")
    schedule = by_uid.get(uid) if is_uid(uid, "sch") else None
    if schedule is None:
        schedule = next((s for s in unused if _signature(s) == _signature(wanted)), None)
    if schedule is None:
        ctx.db.add(wanted)
        if is_uid(uid, "sch") and not ctx.db.query(Schedule).filter(Schedule.uid == uid).first() \
                and all(uid != other.uid for other in kept):
            wanted.uid = uid
        return wanted
    unused[:] = [s for s in unused if s is not schedule]
    schedule.target_type, schedule.target_id = wanted.target_type, wanted.target_id
    schedule.schedule_type, schedule.run_at, schedule.recurrence_rule = wanted.schedule_type, wanted.run_at, wanted.recurrence_rule
    schedule.active = wanted.active
    return schedule


def _apply_schedule(ctx: _Context, file: str, document: dict, channel: str) -> None:
    if document.get("channel", channel) != channel:
        ctx.fail(file, f"« channel » doit valoir {channel}")
        return
    radio = channel.startswith("radio_")
    existing = ctx.db.query(Schedule).filter(Schedule.channel == channel).all()
    by_uid = {s.uid: s for s in existing}
    unused = list(existing)
    kept: list[Schedule] = []
    entries = _list(ctx, file, document, "schedules")
    for uid in config_files._duplicates(e.get("uid") for e in entries if isinstance(e, dict) and is_uid(e.get("uid"))):
        ctx.fail(file, f"uid {uid} présent deux fois")
    for entry in entries:
        entry = entry or {}
        wanted = _wanted_schedule(ctx, file, entry, channel, radio)
        if wanted is None:
            continue
        overrides = _entry_overrides(ctx, file, entry)
        schedule = _place_schedule(ctx, entry, wanted, by_uid, unused, kept)
        _sync_overrides(ctx, schedule, overrides)
        kept.append(schedule)
    removed_ids = [s.id for s in unused]
    for old in unused:
        ctx.db.delete(old)

    async def resync(db: Session) -> None:
        from app.scheduling.jobs import remove_schedule_job, sync_schedule_job

        for schedule_id in removed_ids:
            remove_schedule_job(schedule_id)
        for schedule in db.query(Schedule).filter(Schedule.channel == channel).all():
            sync_schedule_job(schedule)

    ctx.effects.append(resync)


def _sync_overrides(ctx: _Context, schedule: Schedule, wanted: list) -> None:
    from app.scheduling.occurrences import ensure_utc

    current = list(schedule.overrides) if schedule.id is not None else []
    by_uid = {o.uid: o for o in current}
    unused = list(current)
    for uid, date, action, replacement in wanted:
        match = by_uid.get(uid) if is_uid(uid, "ovr") else None
        if match is None:
            match = next((o for o in unused if ensure_utc(o.occurrence_date).date() == ensure_utc(date).date()), None)
        fields = dict(
            occurrence_date=date, action=action,
            replacement_target_type=replacement[0] if replacement else None,
            replacement_target_id=replacement[1] if replacement else None,
        )
        if match is None:
            override = ScheduleOverride(**fields)
            if is_uid(uid, "ovr") and uid not in by_uid and not ctx.db.query(ScheduleOverride).filter(ScheduleOverride.uid == uid).first():
                override.uid = uid
            schedule.overrides.append(override)
        else:
            unused = [o for o in unused if o is not match]
            for key, value in fields.items():
                setattr(match, key, value)
    for old in unused:
        schedule.overrides.remove(old)
