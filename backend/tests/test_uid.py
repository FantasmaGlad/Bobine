"""Identifiants stables : posés à l'insertion, jamais modifiés, remplis pour les bases existantes."""
import os

os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_database.db"
os.environ["BOBINE_MEDIA_DIR"] = "data/test_videos"
os.environ["BOBINE_WATCH_DIR"] = "data/test_watched"
os.environ["BOBINE_THUMBNAILS_DIR"] = "data/test_thumbnails"

import pytest
from sqlalchemy import text

from app import database
from app.database import SessionLocal, init_db
from app.models import Playlist, UidMixin, Base
from app.utils.uid import PREFIXES, is_uid, new_uid


def test_uid_format():
    uid = new_uid("vid")
    assert is_uid(uid) and is_uid(uid, "vid") and not is_uid(uid, "pl")
    for bad in ("vid_zz", "vid-3f9a1c07b2de", "xx_3f9a1c07b2de", 12, None, "vid_3f9a1c07b2de0"):
        assert not is_uid(bad)
    assert len({new_uid("pl") for _ in range(2000)}) == 2000


def test_every_mixin_class_has_a_known_prefix():
    classes = [m.class_ for m in Base.registry.mappers if issubclass(m.class_, UidMixin)]
    assert len(classes) == 13
    assert {c.__uid_prefix__ for c in classes} <= set(PREFIXES) and len({c.__uid_prefix__ for c in classes}) == 13


def test_new_rows_get_a_stable_uid():
    init_db()
    with SessionLocal() as db:
        playlist = Playlist(name="uid-test")
        db.add(playlist)
        db.commit()
        uid = playlist.uid
        assert is_uid(uid, "pl")
        playlist.name = "uid-test renommée"
        db.commit()
        assert playlist.uid == uid
        db.delete(playlist)
        db.commit()


def test_migration_backfills_existing_rows():
    init_db()
    with SessionLocal() as db:
        db.execute(text("INSERT INTO playlists (name, created_at) VALUES ('ancienne', CURRENT_TIMESTAMP)"))
        db.execute(text("UPDATE playlists SET uid = NULL WHERE name = 'ancienne'"))
        db.commit()
    database._migrate_add_uids()
    with SessionLocal() as db:
        row = db.query(Playlist).filter(Playlist.name == "ancienne").one()
        assert is_uid(row.uid, "pl")
        first = row.uid
    database._migrate_add_uids()
    with SessionLocal() as db:
        row = db.query(Playlist).filter(Playlist.name == "ancienne").one()
        assert row.uid == first
        db.delete(row)
        db.commit()
