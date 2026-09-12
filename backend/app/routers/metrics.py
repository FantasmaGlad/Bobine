import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import CourseRating, PlaybackSession, Video
from app.utils.activity_log import log_activity
from app.utils.hardware_info import (
    get_cpu_model_name,
    get_cpu_temp,
    get_gpu_info,
    get_power_watts,
    get_runtime_info,
    get_storage_model,
)
from app.utils.playback_session_tracker import (
    close_playback_session,
    start_playback_session,
    update_playback_session_progress,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


class RatingCreate(BaseModel):
    video_id: int
    rating: int = Field(..., ge=1, le=5)
    channel: str = "cable"
    source: str = "grid"


class RatingResponse(BaseModel):
    id: int
    video_id: int
    rating: int
    channel: str
    source: str
    created_at: datetime


class SessionStartRequest(BaseModel):
    video_id: int
    channel: str = "cable"
    launch_type: str = "grid"
    total_duration_seconds: float = 0.0


class SessionEndRequest(BaseModel):
    session_id: int
    position_seconds: float | None = None
    completed: bool | None = None


def _thumbnail_filename(thumbnail_path: str | None) -> str | None:
    if not thumbnail_path:
        return None
    return thumbnail_path.split("/")[-1]


def _resolve_period_start(period: str) -> datetime | None:
    now = datetime.now(timezone.utc)
    if period == "7d":
        return now - timedelta(days=7)
    if period == "30d":
        return now - timedelta(days=30)
    if period == "this_month":
        return datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    return None  # "all"


@router.post("/ratings", status_code=201)
def create_course_rating(payload: RatingCreate, db: Session = Depends(get_db)):
    """Enregistre l'évaluation 5 étoiles d'un cours vidéo (réf. CDC V3.0.5 Bêta §2.2)."""
    video = db.query(Video).filter(Video.id == payload.video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Vidéo introuvable")

    if payload.channel not in ("cable", "network"):
        payload.channel = "cable"
    if payload.source not in ("grid", "cinema"):
        payload.source = "grid"

    rating = CourseRating(
        video_id=payload.video_id,
        rating=payload.rating,
        channel=payload.channel,
        source=payload.source,
        created_at=datetime.now(timezone.utc),
    )
    db.add(rating)
    db.commit()
    db.refresh(rating)

    log_activity(db, "course_rated", f"{video.title} : {payload.rating} étoiles ({payload.source})")
    return {
        "id": rating.id,
        "video_id": rating.video_id,
        "rating": rating.rating,
        "channel": rating.channel,
        "source": rating.source,
        "created_at": rating.created_at.isoformat(),
    }


@router.get("/ratings")
def list_course_ratings(
    video_id: int | None = None,
    channel: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Liste les évaluations récentes."""
    q = db.query(CourseRating)
    if video_id:
        q = q.filter(CourseRating.video_id == video_id)
    if channel and channel != "all":
        q = q.filter(CourseRating.channel == channel)
    ratings = q.order_by(CourseRating.created_at.desc()).limit(limit).all()

    return [
        {
            "id": r.id,
            "video_id": r.video_id,
            "rating": r.rating,
            "channel": r.channel,
            "source": r.source,
            "created_at": r.created_at.isoformat(),
        }
        for r in ratings
    ]


@router.post("/sessions/start")
def start_session(payload: SessionStartRequest, db: Session = Depends(get_db)):
    """Démarre manuellement une session de lecture."""
    session_id = start_playback_session(
        db,
        video_id=payload.video_id,
        channel=payload.channel,
        launch_type=payload.launch_type,
        total_duration_seconds=payload.total_duration_seconds,
    )
    if not session_id:
        raise HTTPException(status_code=500, detail="Impossible de créer la session")
    return {"session_id": session_id}


@router.post("/sessions/end")
def end_session(payload: SessionEndRequest, db: Session = Depends(get_db)):
    """Clôture manuellement une session de lecture."""
    close_playback_session(
        db,
        session_id=payload.session_id,
        position_seconds=payload.position_seconds,
        completed=payload.completed,
    )
    return {"message": "Session clôturée"}


@router.get("/dashboard")
def get_metrics_dashboard(
    period: str = Query("30d", pattern="^(7d|30d|this_month|all)$"),
    channel: str = Query("all", pattern="^(all|cable|network)$"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Tableau de bord unifié des métriques club et télémétrie matérielle (CDC V3.0.5 Bêta §2.4).
    """
    start_date = _resolve_period_start(period)

    # 1. Filtres pour les requêtes de sessions
    sess_query = db.query(PlaybackSession)
    if start_date:
        sess_query = sess_query.filter(PlaybackSession.started_at >= start_date)
    if channel != "all":
        sess_query = sess_query.filter(PlaybackSession.channel == channel)

    sessions = sess_query.all()

    # 2. Filtres pour les requêtes d'avis
    rating_query = db.query(CourseRating)
    if start_date:
        rating_query = rating_query.filter(CourseRating.created_at >= start_date)
    if channel != "all":
        rating_query = rating_query.filter(CourseRating.channel == channel)

    ratings = rating_query.all()

    # --- Calcul KPIs ---
    total_sessions = len(sessions)
    completed_sessions = sum(1 for s in sessions if s.completed)
    completion_rate = round((completed_sessions / total_sessions) * 100, 1) if total_sessions > 0 else 0.0

    total_played_seconds = sum(s.duration_played_seconds for s in sessions)
    total_broadcast_hours = round(total_played_seconds / 3600.0, 1)
    b_hours = int(total_played_seconds // 3600)
    b_mins = int((total_played_seconds % 3600) // 60)
    formatted_broadcast_time = f"{b_hours}h {b_mins:02d}m" if b_hours > 0 else f"{b_mins}m"

    ratings_count = len(ratings)
    ratings_avg = round(sum(r.rating for r in ratings) / ratings_count, 1) if ratings_count > 0 else 0.0

    distribution = {"5": 0, "4": 0, "3": 0, "2": 0, "1": 0}
    for r in ratings:
        k = str(r.rating)
        if k in distribution:
            distribution[k] += 1

    # Répartition par launch_type
    launch_breakdown = {"grid": 0, "cinema": 0, "schedule": 0, "kiosk": 0}
    for s in sessions:
        lt = s.launch_type or "kiosk"
        if lt in launch_breakdown:
            launch_breakdown[lt] += 1
        else:
            launch_breakdown["kiosk"] += 1

    # --- Histogramme horaire (24 créneaux) ---
    hourly_distribution = [{"hour": h, "count": 0} for h in range(24)]
    for s in sessions:
        # Conversion heure locale
        try:
            local_dt = s.started_at.astimezone() if s.started_at.tzinfo else s.started_at
            h = local_dt.hour
            if 0 <= h < 24:
                hourly_distribution[h]["count"] += 1
        except Exception:
            pass

    # --- Classement des cours ---
    # Indexation par video_id
    video_sessions_map: dict[int, list[PlaybackSession]] = {}
    for s in sessions:
        video_sessions_map.setdefault(s.video_id, []).append(s)

    video_ratings_map: dict[int, list[CourseRating]] = {}
    for r in ratings:
        video_ratings_map.setdefault(r.video_id, []).append(r)

    # Récupérer toutes les vidéos
    all_videos = db.query(Video).all()
    course_stats = []

    for v in all_videos:
        v_sess = video_sessions_map.get(v.id, [])
        v_ratings = video_ratings_map.get(v.id, [])

        v_sess_count = len(v_sess)
        v_ratings_count = len(v_ratings)

        # Si aucun visionnage ni note sur la période, on inclut tout de même avec stats à 0
        v_completed_count = sum(1 for s in v_sess if s.completed)
        v_completion_rate = round((v_completed_count / v_sess_count) * 100, 1) if v_sess_count > 0 else 0.0
        v_avg_rating = round(sum(r.rating for r in v_ratings) / v_ratings_count, 1) if v_ratings_count > 0 else 0.0

        course_stats.append({
            "video_id": v.id,
            "title": v.title,
            "program": v.program or "Autre",
            "release": v.release,
            "duration_seconds": v.duration_seconds or 0,
            "thumbnail_url": _thumbnail_filename(v.thumbnail_path),
            "sessions_count": v_sess_count,
            "completed_count": v_completed_count,
            "completion_rate": v_completion_rate,
            "average_rating": v_avg_rating,
            "ratings_count": v_ratings_count,
        })

    # Tri par popularité (sessions_count desc) par défaut
    course_stats.sort(key=lambda x: (x["sessions_count"], x["average_rating"]), reverse=True)

    # --- Télémétrie Matérielle ---
    gpu_name, gpu_percent, gpu_temp_c = get_gpu_info()
    import shutil
    disk_usage = shutil.disk_usage("/")
    used_pct = round((disk_usage.used / disk_usage.total) * 100, 1) if disk_usage.total else 0.0

    hardware = {
        "cpu_name": get_cpu_model_name(),
        "cpu_temp_c": get_cpu_temp(),
        "gpu_name": gpu_name,
        "gpu_percent": gpu_percent,
        "gpu_temp_c": gpu_temp_c,
        "power_watts": get_power_watts(),
        "storage_model": get_storage_model(),
        "storage_used_percent": used_pct,
        "storage_free_bytes": disk_usage.free,
        "storage_total_bytes": disk_usage.total,
        "runtime": get_runtime_info(),
    }

    return {
        "period": period,
        "channel": channel,
        "kpis": {
            "satisfaction": {
                "average": ratings_avg,
                "total_count": ratings_count,
                "distribution": distribution,
            },
            "completion": {
                "rate": completion_rate,
                "total_sessions": total_sessions,
                "completed_sessions": completed_sessions,
            },
            "broadcast": {
                "total_hours": total_broadcast_hours,
                "total_seconds": total_played_seconds,
                "formatted": formatted_broadcast_time,
            },
            "sessions": {
                "total": total_sessions,
                "breakdown": launch_breakdown,
            },
        },
        "hourly_distribution": hourly_distribution,
        "course_stats": course_stats,
        "hardware": hardware,
    }
