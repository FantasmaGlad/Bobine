"""Migrations du schéma SQLite appliquées au démarrage, idempotentes."""

import logging
import uuid
from pathlib import Path

from sqlalchemy.exc import OperationalError

from app import database
from app.models import Base

logger = logging.getLogger(__name__)


def migrate_add_uids():
    from sqlalchemy import text

    from app.models import UidMixin
    from app.utils.uid import new_uid

    if not database._IS_SQLITE:
        return
    with database.engine.connect() as conn:
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


def migrate_storage_indexes():
    from sqlalchemy import text

    if not database._IS_SQLITE:
        return
    with database.engine.connect() as conn:
        for table in ("videos", "audio_tracks", "radio_tracks"):
            conn.execute(text(f"CREATE INDEX IF NOT EXISTS ix_{table}_storage_id ON {table}(storage_id)"))
        conn.commit()


def migrate_audio_playlist_items_to_tracks():
    from sqlalchemy import text

    if not database._IS_SQLITE:
        return

    with database.engine.connect() as conn:
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


def migrate_add_missing_columns():
    from sqlalchemy import text
    from sqlalchemy.exc import OperationalError

    if not database._IS_SQLITE:
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
    with database.engine.connect() as conn:
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


def migrate_drop_devices_access_settings():
    from sqlalchemy import text

    if not database._IS_SQLITE:
        return
    with database.engine.connect() as conn:
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


def migrate_update_channel_beta_to_canary():
    from sqlalchemy import text

    if not database._IS_SQLITE:
        return

    with database.engine.connect() as conn:
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


def migrate_schedule_radio_channel_to_network():
    from sqlalchemy import text

    if not database._IS_SQLITE:
        return

    with database.engine.connect() as conn:
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


RADIO_OUTPUTS_MARK = "migration_radio_outputs"
_RADIO_KEY_PREFIXES = ("radio_sound_", "radio_mix_", "radio_default_playlist_id_")
_RULE_COLUMNS = "rule_type, n_tracks, interval_minutes, times_of_day, enabled, created_at"


def migrate_radio_outputs():
    """La radio réseau devient celle de Réseau 2, une seule fois : planning, règles, réglages et route audio ; règles « les deux » recopiées sur chaque ancienne sortie."""
    from sqlalchemy import text

    if not database._IS_SQLITE:
        return
    with database.engine.begin() as conn:
        tables = {row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
        if not {"settings", "schedules", "radio_announcement_rules"} <= tables:
            return
        if conn.execute(text("SELECT 1 FROM settings WHERE key = :key"), {"key": RADIO_OUTPUTS_MARK}).first():
            return
        moved = conn.execute(text("UPDATE schedules SET channel='radio_network_2' WHERE channel='radio_network'")).rowcount
        conn.execute(text("UPDATE radio_announcement_rules SET target='radio_network_2' WHERE target IN ('radio_network', 'radio')"))
        conn.execute(text(
            f"INSERT INTO radio_announcement_rules ({_RULE_COLUMNS}, target) "
            f"SELECT {_RULE_COLUMNS}, 'radio_network_2' FROM radio_announcement_rules WHERE target = 'both'"
        ))
        conn.execute(text("UPDATE radio_announcement_rules SET target='radio_cable' WHERE target = 'both'"))
        for prefix in _RADIO_KEY_PREFIXES:
            conn.execute(text("UPDATE settings SET key = :new WHERE key = :old"),
                         {"new": f"{prefix}radio_network_2", "old": f"{prefix}radio_network"})
        _move_audio_route(conn)
        conn.execute(text("INSERT OR IGNORE INTO settings (key, value) VALUES ('display_output_network_2', 'radio')"))
        conn.execute(text("INSERT INTO settings (key, value) VALUES (:key, '1')"), {"key": RADIO_OUTPUTS_MARK})
    logger.info(f"Migration : radio réseau rattachée à Réseau 2 ({moved} programmation(s))")


def _move_audio_route(conn) -> None:
    import json

    from sqlalchemy import text

    from app.devices.routing import ROUTES_SETTING

    row = conn.execute(text("SELECT value FROM settings WHERE key = :key"), {"key": ROUTES_SETTING}).first()
    try:
        routes = json.loads(row[0]) if row and row[0] else {}
    except ValueError:
        logger.warning("Migration : routes audio illisibles, laissées telles quelles")
        return
    if not isinstance(routes, dict) or "radio_network" not in routes:
        return
    routes["radio_network_2"] = routes.pop("radio_network")
    conn.execute(text("UPDATE settings SET value = :value WHERE key = :key"), {"value": json.dumps(routes), "key": ROUTES_SETTING})

def migrate_backfill_video_metadata():
    if not database._IS_SQLITE:
        return
    try:
        from app.models import Video
        from app.utils.video_utils.probe import extract_metadata

        with database.SessionLocal() as db:
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


def migrate_backfill_audio_duration():
    if not database._IS_SQLITE:
        return
    try:
        from app.models import AudioTrack, RadioTrack
        from app.utils.audio_utils import extract_audio_duration

        with database.SessionLocal() as db:
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
