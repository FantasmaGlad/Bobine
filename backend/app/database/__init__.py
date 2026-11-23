import logging
import time
from pathlib import Path


from sqlalchemy import create_engine, event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from app.catalog.fold import fold
from app.config import settings
from app.models import Base

logger = logging.getLogger(__name__)

_IS_SQLITE = settings.database_url.startswith("sqlite")

connect_args = {}
if _IS_SQLITE:
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_size=5,
    max_overflow=5,
    pool_timeout=30,
    pool_recycle=3600,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    if not _IS_SQLITE:
        return
    dbapi_connection.create_function("bobine_fold", 1, fold, deterministic=True)
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA cache_size=-64000")
    cursor.execute("PRAGMA busy_timeout=30000")
    from app.database import foreign_keys

    if foreign_keys.enforced:
        cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


class RetryingSession(Session):
    """Filet de sécurité au-dessus de busy_timeout."""

    _MAX_RETRIES = 3
    _BASE_DELAY_SECONDS = 0.2

    def commit(self):
        attempt = 0
        while True:
            try:
                return super().commit()
            except OperationalError as e:
                if not _IS_SQLITE or "locked" not in str(e).lower() or attempt >= self._MAX_RETRIES:
                    raise
                self.rollback()
                delay = self._BASE_DELAY_SECONDS * (2 ** attempt)
                logger.warning(
                    f"Base SQLite verrouillée, nouvelle tentative dans {delay:.1f}s "
                    f"(essai {attempt + 1}/{self._MAX_RETRIES})"
                )
                time.sleep(delay)
                attempt += 1


SessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine,
    class_=RetryingSession,
)


def release_sqlite_files(db_path: Path) -> None:
    """Vide le journal WAL, ferme le pool et supprime `-wal` et `-shm` avant de remplacer ou d'effacer la base."""
    from sqlalchemy import text

    try:
        with engine.connect() as conn:
            conn.execute(text("PRAGMA wal_checkpoint(TRUNCATE);"))
    except Exception as exc:
        logger.warning("Checkpoint WAL impossible avant de détacher la base : %s", exc)
    engine.dispose()
    for suffix in ("-wal", "-shm"):
        Path(f"{db_path}{suffix}").unlink(missing_ok=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    if _IS_SQLITE:
        from app.database import foreign_keys

        foreign_keys.suspend(engine)
    from pathlib import Path
    for path_str in [
        settings.media_dir,
        settings.watch_dir,
        settings.thumbnails_dir,
        settings.backgrounds_dir,
        settings.backgrounds_watch_dir,
        settings.visuals_dir,
        settings.visuals_watch_dir,
        settings.audio_dir,
        settings.audio_watch_dir,
        settings.radio_dir,
        settings.radio_covers_dir,
        settings.radio_announcements_dir,
        settings.radio_watch_dir,
        settings.logs_dir,
        settings.subtitles_dir,
    ]:
        Path(path_str).mkdir(parents=True, exist_ok=True)

    if settings.database_url.startswith("sqlite:///"):
        db_path = Path(settings.database_url[len("sqlite:///"):])
        db_path.parent.mkdir(parents=True, exist_ok=True)

    from app.database import migrations

    migrations.migrate_audio_playlist_items_to_tracks()
    Base.metadata.create_all(bind=engine)
    migrations.migrate_add_missing_columns()
    migrations.migrate_backfill_video_metadata()
    migrations.migrate_backfill_audio_duration()
    migrations.migrate_update_channel_beta_to_canary()
    migrations.migrate_schedule_radio_channel_to_network()
    migrations.migrate_radio_outputs()
    migrations.migrate_schedule_lanes_to_outputs()
    migrations.migrate_storage_indexes()
    migrations.migrate_drop_devices_access_settings()
    migrations.migrate_add_uids()
    if _IS_SQLITE:
        from app.database.foreign_keys import align_foreign_keys

        align_foreign_keys(engine)
