import logging
import time
from pathlib import Path

import uuid

from sqlalchemy import create_engine, event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
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
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA cache_size=-64000")
    cursor.execute("PRAGMA busy_timeout=30000")
    from app import foreign_keys

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
        from app import foreign_keys

        foreign_keys.suspend(engine)
    from pathlib import Path
    for path_str in [
        settings.media_dir,
        settings.watch_dir,
        settings.thumbnails_dir,
        settings.backgrounds_dir,
        settings.backgrounds_watch_dir,
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

    _migrate_audio_playlist_items_to_tracks()
    Base.metadata.create_all(bind=engine)
    _migrate_add_missing_columns()
    _migrate_backfill_video_metadata()
    _migrate_backfill_audio_duration()
    _migrate_update_channel_beta_to_canary()
    _migrate_schedule_radio_channel_to_network()
    _migrate_storage_indexes()
    _migrate_drop_devices_access_settings()
    _migrate_add_uids()
    if _IS_SQLITE:
        from app.foreign_keys import align_foreign_keys

        align_foreign_keys(engine)


def _migrate_add_uids():
    from sqlalchemy import text

    from app.models import UidMixin
    from app.utils.uid import new_uid

    if not _IS_SQLITE:
        return
    with engine.connect() as conn:
        for mapper in Base.registry.mappers:
            cls = mapper.class_
            if not issubclass(cls, UidMixin):
                continue
            table = cls.__tablename__
            columns = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}
            if "uid" not in columns:
                try:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN uid VARCHAR(32)"))
                except OperationalError:
                    pass
            for (row_id,) in conn.execute(text(f"SELECT id FROM {table} WHERE uid IS NULL")).fetchall():
                conn.execute(text(f"UPDATE {table} SET uid = :uid WHERE id = :id"), {"uid": new_uid(cls.__uid_prefix__), "id": row_id})
            conn.execute(text(f"CREATE UNIQUE INDEX IF NOT EXISTS ix_{table}_uid ON {table}(uid)"))
        conn.execute(text("INSERT OR IGNORE INTO settings (key, value) VALUES ('instance_uid', :uid)"), {"uid": uuid.uuid4().hex[:16]})
        conn.commit()


def _migrate_storage_indexes():
    from sqlalchemy import text

    if not _IS_SQLITE:
        return
    with engine.connect() as conn:
        for table in ("videos", "audio_tracks", "radio_tracks"):
            conn.execute(text(f"CREATE INDEX IF NOT EXISTS ix_{table}_storage_id ON {table}(storage_id)"))
        conn.commit()


def _migrate_audio_playlist_items_to_tracks():
    from sqlalchemy import text

    if not _IS_SQLITE:
        return

    with engine.connect() as conn:
        tables = {row[0] for row in conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='audio_playlist_items'"
        ))}
        if "audio_playlist_items" not in tables:
            return

        columns = {row[1] for row in conn.execute(text("PRAGMA table_info(audio_playlist_items)"))}
        if "audio_track_id" in columns:
            return

        count = conn.execute(text("SELECT COUNT(*) FROM audio_playlist_items")).scalar()
        if count:
            logger.warning(
                f"Migration audio_playlist_items impossible : {count} ligne(s) existante(s) "
                "avec l'ancien schéma (audio_course_id) et aucune correspondance automatique "
                "vers audio_track_id — laissées telles quelles."
            )
            return

        conn.execute(text("DROP TABLE audio_playlist_items"))
        conn.commit()
        logger.info("Migration : table audio_playlist_items recréée avec le schéma piste par piste")


def _migrate_add_missing_columns():
    from sqlalchemy import text
    from sqlalchemy.exc import OperationalError

    if not _IS_SQLITE:
        return

    wanted = [
        ("schedules", "channel", "VARCHAR NOT NULL DEFAULT 'cable'"),
        ("playback_state", "channel", "VARCHAR NOT NULL DEFAULT 'cable'"),
        ("playback_state", "target_type", "VARCHAR"),
        ("playback_state", "target_id", "INTEGER"),
        ("audio_playlist_items", "background_id", "INTEGER REFERENCES backgrounds(id)"),
        ("audio_tracks", "background_id", "INTEGER REFERENCES backgrounds(id)"),
        ("videos", "description", "TEXT"),
        ("videos", "audio_channels", "INTEGER"),
        ("videos", "audio_codec", "VARCHAR"),
        ("videos", "fps", "FLOAT"),
        ("videos", "bitrate_kbps", "INTEGER"),
        ("videos", "pix_fmt", "VARCHAR"),
        ("videos", "web_path", "VARCHAR"),
        ("videos", "web_status", "VARCHAR"),
        ("videos", "chapters_source", "TEXT"),
        ("videos", "chapters_file", "TEXT"),
        ("system_metrics_history", "extra_data", "TEXT"),
        ("radio_announcement_rules", "target", "VARCHAR NOT NULL DEFAULT 'radio_network'"),
        ("videos", "storage_id", "INTEGER REFERENCES external_volumes(id)"),
        ("videos", "rel_path", "VARCHAR"),
        ("audio_tracks", "storage_id", "INTEGER REFERENCES external_volumes(id)"),
        ("audio_tracks", "rel_path", "VARCHAR"),
        ("radio_tracks", "storage_id", "INTEGER REFERENCES external_volumes(id)"),
        ("radio_tracks", "rel_path", "VARCHAR"),
    ]
    with engine.connect() as conn:
        for table, column, ddl in wanted:
            existing = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}
            if column in existing:
                continue
            try:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
                conn.commit()
                logger.info(f"Migration : colonne {table}.{column} ajoutée")
            except OperationalError as e:
                conn.rollback()
                if "duplicate column name" not in str(e).lower():
                    raise
                logger.info(
                    f"Migration : colonne {table}.{column} déjà ajoutée par un autre worker, ignoré"
                )


def _migrate_drop_devices_access_settings():
    from sqlalchemy import text

    if not _IS_SQLITE:
        return
    with engine.connect() as conn:
        tables = {row[0] for row in conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='settings'"
        ))}
        if "settings" not in tables:
            return
        result = conn.execute(text(
            "DELETE FROM settings WHERE key IN ('devices_pin_hash', 'devices_enabled')"
        ))
        conn.commit()
        if result.rowcount:
            logger.info(f"Migration : {result.rowcount} réglage(s) d'accès aux périphériques retiré(s)")


def _migrate_update_channel_beta_to_canary():
    from sqlalchemy import text

    if not _IS_SQLITE:
        return

    with engine.connect() as conn:
        tables = {row[0] for row in conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='settings'"
        ))}
        if "settings" not in tables:
            return
        result = conn.execute(text(
            "UPDATE settings SET value='canary' WHERE key='update_channel' AND value='beta'"
        ))
        conn.commit()
        if result.rowcount:
            logger.info(
                f"Migration : canal de mise à jour 'beta' (rolling) renommé 'canary' "
                f"({result.rowcount} réglage(s))"
            )


def _migrate_schedule_radio_channel_to_network():
    from sqlalchemy import text

    if not _IS_SQLITE:
        return

    with engine.connect() as conn:
        tables = {row[0] for row in conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schedules'"
        ))}
        if "schedules" not in tables:
            return
        result = conn.execute(text(
            "UPDATE schedules SET channel='radio_network' WHERE channel='radio'"
        ))
        conn.commit()
        if result.rowcount:
            logger.info(
                f"Migration : planning radio historique rattaché à la sortie réseau "
                f"({result.rowcount} programmation(s))"
            )


def _migrate_backfill_video_metadata():
    if not _IS_SQLITE:
        return
    try:
        from app.models import Video
        from app.utils.video_utils.probe import extract_metadata

        with SessionLocal() as db:
            videos = db.query(Video).filter(
                Video.audio_channels.is_(None) | (Video.pix_fmt.is_(None) & Video.codec.isnot(None))
            ).all()
            if not videos:
                return
            updated = 0
            for v in videos:
                if not v.file_path or not Path(v.file_path).exists():
                    continue
                try:
                    meta = extract_metadata(v.file_path)
                    v.audio_channels = meta.get("audio_channels")
                    v.audio_codec = meta.get("audio_codec")
                    v.fps = meta.get("fps")
                    v.bitrate_kbps = meta.get("bitrate_kbps")
                    v.pix_fmt = meta.get("pix_fmt") or v.pix_fmt
                    if not v.description and meta.get("description"):
                        v.description = meta.get("description")
                    if not v.width and meta.get("width"):
                        v.width = meta.get("width")
                    if not v.height and meta.get("height"):
                        v.height = meta.get("height")
                    if not v.codec and meta.get("codec"):
                        v.codec = meta.get("codec")
                    updated += 1
                except Exception as e:
                    logger.debug(f"Rétro-migration métadonnées ignorée pour {v.file_path}: {e}")
            if updated > 0:
                db.commit()
                logger.info(f"Migration : métadonnées enrichies pour {updated} vidéo(s) existante(s)")
    except Exception as e:
        logger.warning(f"Avertissement lors de la rétro-migration des métadonnées vidéo : {e}")


def _migrate_backfill_audio_duration():
    if not _IS_SQLITE:
        return
    try:
        from app.models import AudioTrack, RadioTrack
        from app.utils.audio_utils import extract_audio_duration

        with SessionLocal() as db:
            tracks = db.query(AudioTrack).filter(AudioTrack.duration_seconds.is_(None)).all()
            updated = 0
            for t in tracks:
                if not t.file_path or not Path(t.file_path).exists():
                    continue
                dur = extract_audio_duration(t.file_path)
                if dur:
                    t.duration_seconds = dur
                    updated += 1

            radio_tracks = db.query(RadioTrack).filter(RadioTrack.duration_seconds.is_(None)).all()
            for rt in radio_tracks:
                if not rt.file_path or not Path(rt.file_path).exists():
                    continue
                dur = extract_audio_duration(rt.file_path)
                if dur:
                    rt.duration_seconds = dur
                    updated += 1

            if updated > 0:
                db.commit()
                logger.info(f"Migration : durée enrichie pour {updated} piste(s) audio/radio")
    except Exception as e:
        logger.warning(f"Avertissement lors de la rétro-migration des durées audio : {e}")
