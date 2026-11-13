from typing import List
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.responses import CourseRatingEntry, Message, SessionStarted
from app.api.contract import CHANNELS, DASHBOARD_CHANNELS, DEFAULT_CHANNEL, DASHBOARD_PERIODS, HISTORY_PERIODS, regex
from app.database import get_db
from app.models import CourseRating, Video
from app.metrics.dashboard import build_dashboard
from app.metrics.history import hardware_history
from app.utils.activity_log import log_activity
from app.utils.playback_session_tracker import (
    close_playback_session,
    start_playback_session,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


class RatingCreate(BaseModel):
    video_id: int
    rating: int = Field(..., ge=1, le=5)
    channel: str = DEFAULT_CHANNEL
    source: str = "grid"


class SessionStartRequest(BaseModel):
    video_id: int
    channel: str = DEFAULT_CHANNEL
    launch_type: str = "grid"
    total_duration_seconds: float = 0.0


class SessionEndRequest(BaseModel):
    session_id: int
    position_seconds: float | None = None
    completed: bool | None = None


@router.post("/ratings", status_code=201, response_model=CourseRatingEntry)
def create_course_rating(payload: RatingCreate, db: Session = Depends(get_db)):
    """Enregistre l'évaluation 5 étoiles d'un cours vidéo."""
    video = db.query(Video).filter(Video.id == payload.video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Vidéo introuvable")

    if payload.channel not in CHANNELS:
        payload.channel = DEFAULT_CHANNEL
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


@router.get("/ratings", response_model=List[CourseRatingEntry])
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


@router.post("/sessions/start", response_model=SessionStarted)
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


@router.post("/sessions/end", response_model=Message)
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
    period: str = Query("30d", pattern=regex(DASHBOARD_PERIODS)),
    channel: str = Query("all", pattern=regex(DASHBOARD_CHANNELS)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Tableau de bord unifié des métriques club et télémétrie matérielle."""
    return build_dashboard(db, period, channel)


@router.get("/hardware/history")
def get_hardware_history(
    metric: str = Query("cpu", pattern="^[a-zA-Z0-9_]+$"),
    period: str = Query("1h", pattern=regex(HISTORY_PERIODS)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Historique temporel d'une métrique matérielle (1h, 6h, 24h, 7j, 30j, mois en cours, tout l'historique conservé) avec statistiques et points échantillonnés."""
    return hardware_history(db, metric, period)

