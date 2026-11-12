import logging

from sqlalchemy.orm import Session

from app.models import ActivityLog

logger = logging.getLogger(__name__)


def log_activity(db: Session, event_type: str, detail: str | None = None) -> None:
    """Enregistre un évènement dans le log d'activité, consultable depuis l'interface : téléversements, imports, lectures, playlists, programmations, overrides."""
    try:
        db.add(ActivityLog(event_type=event_type, detail=detail))
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Échec de l'écriture du log d'activité ({event_type}): {e}")
