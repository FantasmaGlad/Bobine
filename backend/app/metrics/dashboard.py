"""Tableau de bord : satisfaction, complétion, diffusion, fréquentation et classement des cours."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.hardware.telemetry import get_system_telemetry_payload
from app.models import CourseRating, PlaybackSession, Video

logger = logging.getLogger(__name__)

_LAUNCH_TYPES = ("grid", "cinema", "schedule", "kiosk")


def _percent(part: int, whole: int) -> float:
    return round(part / whole * 100, 1) if whole > 0 else 0.0


def _average(values: list[int]) -> float:
    return round(sum(values) / len(values), 1) if values else 0.0


def thumbnail_filename(thumbnail_path: str | None) -> str | None:
    return thumbnail_path.split("/")[-1] if thumbnail_path else None


def period_start(period: str) -> datetime | None:
    now = datetime.now(timezone.utc)
    if period == "7d":
        return now - timedelta(days=7)
    if period == "30d":
        return now - timedelta(days=30)
    if period == "this_month":
        return datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    return None


def _filtered(db: Session, model, stamp, start: datetime | None, channel: str) -> list:
    query = db.query(model)
    if start:
        query = query.filter(stamp >= start)
    if channel != "all":
        query = query.filter(model.channel == channel)
    return query.all()


def _broadcast(sessions: list[PlaybackSession]) -> dict[str, Any]:
    seconds = sum(s.duration_played_seconds for s in sessions)
    hours, minutes = int(seconds // 3600), int(seconds % 3600 // 60)
    return {
        "total_hours": round(seconds / 3600.0, 1),
        "total_seconds": seconds,
        "formatted": f"{hours}h {minutes:02d}m" if hours > 0 else f"{minutes}m",
    }


def _launch_breakdown(sessions: list[PlaybackSession]) -> dict[str, int]:
    breakdown = dict.fromkeys(_LAUNCH_TYPES, 0)
    for session in sessions:
        kind = session.launch_type or "kiosk"
        breakdown[kind if kind in breakdown else "kiosk"] += 1
    return breakdown


def _hourly(sessions: list[PlaybackSession]) -> list[dict[str, int]]:
    hours = [{"hour": h, "count": 0} for h in range(24)]
    for session in sessions:
        try:
            started = session.started_at.astimezone() if session.started_at.tzinfo else session.started_at
            hours[started.hour]["count"] += 1
        except Exception as exc:
            logger.debug("get_metrics_dashboard : %s", exc)
    return hours


def _course_entry(video: Video, sessions: list[PlaybackSession], ratings: list[CourseRating]) -> dict[str, Any]:
    completed = sum(1 for s in sessions if s.completed)
    thumbnail = thumbnail_filename(video.thumbnail_path)
    return {
        "video_id": video.id,
        "title": video.title,
        "program": video.program or "Autre",
        "release": video.release,
        "duration_seconds": video.duration_seconds or 0,
        "total_duration_hours": round((video.duration_seconds or 0) * len(sessions) / 3600.0, 1),
        "thumbnail_path": thumbnail,
        "thumbnail_url": thumbnail,
        "sessions_count": len(sessions),
        "total_sessions": len(sessions),
        "completed_count": completed,
        "completed_sessions": completed,
        "completion_rate": _percent(completed, len(sessions)),
        "average_rating": _average([r.rating for r in ratings]),
        "ratings_count": len(ratings),
    }


def _course_stats(db: Session, sessions: list[PlaybackSession], ratings: list[CourseRating]) -> list[dict[str, Any]]:
    by_video: dict[int, list[PlaybackSession]] = {}
    for session in sessions:
        by_video.setdefault(session.video_id, []).append(session)
    rated: dict[int, list[CourseRating]] = {}
    for rating in ratings:
        rated.setdefault(rating.video_id, []).append(rating)
    stats = [_course_entry(v, by_video.get(v.id, []), rated.get(v.id, [])) for v in db.query(Video).all()]
    stats.sort(key=lambda x: (x["sessions_count"], x["average_rating"]), reverse=True)
    return stats


def build_dashboard(db: Session, period: str, channel: str) -> dict[str, Any]:
    start = period_start(period)
    sessions = _filtered(db, PlaybackSession, PlaybackSession.started_at, start, channel)
    ratings = _filtered(db, CourseRating, CourseRating.created_at, start, channel)
    total, completed = len(sessions), sum(1 for s in sessions if s.completed)
    distribution = {str(star): 0 for star in range(5, 0, -1)}
    for rating in ratings:
        if str(rating.rating) in distribution:
            distribution[str(rating.rating)] += 1
    average = _average([r.rating for r in ratings])
    broadcast = _broadcast(sessions)
    hourly = _hourly(sessions)
    peak = max(h["count"] for h in hourly)
    courses = _course_stats(db, sessions, ratings)
    hardware = get_system_telemetry_payload()
    return {
        "period": period,
        "channel": channel,
        "kpis": {
            "satisfaction": {"average": average, "total_count": len(ratings), "distribution": distribution},
            "completion": {"rate": _percent(completed, total), "total_sessions": total, "completed_sessions": completed},
            "broadcast": broadcast,
            "sessions": {"total": total, "breakdown": _launch_breakdown(sessions)},
            "average_satisfaction": average,
            "ratings_count": len(ratings),
            "completion_rate": _percent(completed, total),
            "total_broadcast_hours": broadcast["total_hours"],
            "total_sessions": total,
            "completed_sessions": completed,
        },
        "rating_breakdown": [{"score": int(star), "count": count, "percentage": _percent(count, len(ratings))}
                             for star, count in distribution.items()],
        "hourly_distribution": hourly,
        "hourly_attendance": [{"hour": h["hour"], "sessions": h["count"]} for h in hourly],
        "peak_hours": [h["hour"] for h in hourly if h["count"] == peak and peak > 0],
        "course_stats": courses,
        "top_courses": courses,
        "hardware": hardware,
        "hardware_telemetry": hardware,
    }
