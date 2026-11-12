"""Dernier lancement programmé de chaque canal, conservé en base pour survivre à un redémarrage."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models import ScheduledLaunch


def remember(db: Session, channel: str, target_type: str, target_id: int, started_at: datetime) -> None:
    """Enregistre le lancement en cours du canal ; il remplace le précédent."""
    db.query(ScheduledLaunch).filter(ScheduledLaunch.channel == channel).delete()
    db.add(ScheduledLaunch(channel=channel, target_type=target_type, target_id=target_id, started_at=started_at, active=True))
    db.commit()


def close(db: Session, channel: str) -> None:
    """Le lancement du canal n'est plus à l'écran (arrêt, autre lecture) : il ne sera pas repris."""
    db.query(ScheduledLaunch).filter(ScheduledLaunch.channel == channel, ScheduledLaunch.active.is_(True)).update(
        {ScheduledLaunch.active: False}
    )
    db.commit()


def get(db: Session, channel: str) -> ScheduledLaunch | None:
    return db.query(ScheduledLaunch).filter(ScheduledLaunch.channel == channel).first()
