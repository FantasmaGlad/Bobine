import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models import PlaybackSession, Video

logger = logging.getLogger(__name__)


def start_playback_session(
    db: Session,
    video_id: int,
    channel: str = "cable",
    launch_type: str = "kiosk",
    total_duration_seconds: float = 0.0,
) -> int | None:
    """
    Crée et persiste une nouvelle session de lecture pour le suivi d'assiduité (CDC V3.0.5 §2.3).
    Retourne l'ID de la session créée.
    """
    try:
        # Si total_duration_seconds non fourni, tentative de récupération depuis la vidéo
        if not total_duration_seconds or total_duration_seconds <= 0:
            video = db.query(Video).filter(Video.id == video_id).first()
            if video and video.duration_seconds:
                total_duration_seconds = float(video.duration_seconds)

        session = PlaybackSession(
            video_id=video_id,
            channel=channel,
            started_at=datetime.now(timezone.utc),
            ended_at=None,
            duration_played_seconds=0.0,
            total_duration_seconds=float(total_duration_seconds or 0.0),
            completed=False,
            launch_type=launch_type,
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        logger.info(
            f"Session de lecture #{session.id} créée (vidéo {video_id}, canal {channel}, type {launch_type})"
        )
        return session.id
    except Exception as e:
        db.rollback()
        logger.error(f"Erreur lors de la création de la session de lecture : {e}")
        return None


def update_playback_session_progress(
    db: Session,
    session_id: int,
    position_seconds: float,
) -> None:
    """Met à jour silencieusement la durée de visionnage atteinte."""
    try:
        session = db.query(PlaybackSession).filter(PlaybackSession.id == session_id).first()
        if not session or session.ended_at is not None:
            return

        if position_seconds > session.duration_played_seconds:
            session.duration_played_seconds = round(float(position_seconds), 1)

        if session.total_duration_seconds > 0:
            ratio = session.duration_played_seconds / session.total_duration_seconds
            if ratio >= 0.90:
                session.completed = True

        db.commit()
    except Exception as e:
        db.rollback()
        logger.debug(f"Erreur lors de la mise à jour de la session #{session_id} : {e}")


def close_playback_session(
    db: Session,
    session_id: int,
    position_seconds: float | None = None,
    completed: bool | None = None,
) -> None:
    """Clôture la session de lecture et calcule le statut d'achèvement définitif."""
    try:
        session = db.query(PlaybackSession).filter(PlaybackSession.id == session_id).first()
        if not session or session.ended_at is not None:
            return

        session.ended_at = datetime.now(timezone.utc)

        if position_seconds is not None and position_seconds > session.duration_played_seconds:
            session.duration_played_seconds = round(float(position_seconds), 1)

        if completed is not None:
            session.completed = completed
        elif session.total_duration_seconds > 0:
            session.completed = (session.duration_played_seconds / session.total_duration_seconds) >= 0.90

        db.commit()
        logger.info(
            f"Session de lecture #{session.id} clôturée (durée {session.duration_played_seconds:.1f}s / "
            f"{session.total_duration_seconds:.1f}s, complétée={session.completed})"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Erreur lors de la clôture de la session #{session_id} : {e}")
