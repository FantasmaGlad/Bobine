"""Écritures en base liées à la lecture (sessions de visionnage, lancement programmé) : jamais bloquantes."""
import logging

logger = logging.getLogger(__name__)


def _db_start_session(video_id: int, channel: str, launch_type: str, duration: float) -> int | None:
    try:
        from app.database import SessionLocal
        from app.utils.playback_session_tracker import start_playback_session
        with SessionLocal() as db:
            return start_playback_session(db, video_id, channel, launch_type, duration)
    except Exception as e:
        logger.error(f"Erreur DB start session : {e}")
        return None


def _db_update_session(session_id: int, position: float) -> None:
    try:
        from app.database import SessionLocal
        from app.utils.playback_session_tracker import update_playback_session_progress
        with SessionLocal() as db:
            update_playback_session_progress(db, session_id, position)
    except Exception as e:
        logger.debug(f"Erreur DB update session : {e}")


def _db_close_scheduled_launch(channel: str) -> None:
    try:
        from app.database import SessionLocal
        from app.scheduling import launch_store as scheduled_launch_store
        with SessionLocal() as db:
            scheduled_launch_store.close(db, channel)
    except Exception as e:
        logger.error(f"Erreur DB clôture du lancement programmé : {e}")


def _db_close_session(session_id: int, position: float | None = None, completed: bool | None = None) -> None:
    try:
        from app.database import SessionLocal
        from app.utils.playback_session_tracker import close_playback_session
        with SessionLocal() as db:
            close_playback_session(db, session_id, position, completed)
    except Exception as e:
        logger.error(f"Erreur DB close session : {e}")
