"""Clés étrangères : une base créée avant les règles de suppression est alignée sur le modèle, ses orphelins retirés."""
import sqlite3

from sqlalchemy import create_engine, event

from app.foreign_keys import align_foreign_keys
from app.models import Base


def _engine(path):
    engine = create_engine(f"sqlite:///{path}")

    @event.listens_for(engine, "connect")
    def _on(dbapi_connection, _):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    return engine


def _old_schema(path):
    """Base au schéma du modèle, mais dont deux tables ont des clés sans action, comme avant les règles."""
    Base.metadata.create_all(create_engine(f"sqlite:///{path}"))
    db = sqlite3.connect(path)
    db.executescript(
        """
        PRAGMA foreign_keys=OFF;
        DROP TABLE playlist_items;
        CREATE TABLE playlist_items (
            id INTEGER NOT NULL PRIMARY KEY,
            playlist_id INTEGER NOT NULL REFERENCES playlists (id),
            video_id INTEGER NOT NULL REFERENCES videos (id),
            position INTEGER NOT NULL
        );
        CREATE INDEX ix_old_playlist_items_position ON playlist_items (position);
        DROP TABLE audio_courses;
        CREATE TABLE audio_courses (
            id INTEGER NOT NULL PRIMARY KEY, title VARCHAR NOT NULL, program VARCHAR,
            background_id INTEGER REFERENCES backgrounds (id), imported_at DATETIME, uid VARCHAR(32)
        );
        INSERT INTO videos (id, file_path, title, source, imported_at) VALUES (1, 'a.mp4', 'A', 'upload', '2026-11-12');
        INSERT INTO playlists (id, name, created_at) VALUES (1, 'P', '2026-11-12');
        INSERT INTO playlist_items VALUES (1, 1, 1, 0);
        INSERT INTO playlist_items VALUES (2, 1, 99, 1);
        INSERT INTO backgrounds (id, file_path, title, imported_at) VALUES (1, 'b.mp4', 'B', '2026-11-12');
        INSERT INTO audio_courses (id, title, background_id) VALUES (1, 'Cours', 1);
        INSERT INTO audio_courses (id, title, background_id) VALUES (2, 'Orphelin', 42);
        """
    )
    db.commit()
    db.close()


def _actions(db, table):
    return {(row[3], row[2]): row[6] for row in db.execute(f"PRAGMA foreign_key_list({table})")}


def test_old_tables_get_the_model_rules_and_lose_their_orphans(tmp_path):
    path = tmp_path / "ancienne.db"
    _old_schema(path)
    align_foreign_keys(_engine(path))

    db = sqlite3.connect(path)
    assert _actions(db, "playlist_items") == {("playlist_id", "playlists"): "CASCADE", ("video_id", "videos"): "CASCADE"}
    assert _actions(db, "audio_courses") == {("background_id", "backgrounds"): "SET NULL"}
    # La ligne qui visait une vidéo disparue est retirée ; la colonne facultative est vidée.
    assert db.execute("SELECT id FROM playlist_items").fetchall() == [(1,)]
    assert db.execute("SELECT id, background_id FROM audio_courses ORDER BY id").fetchall() == [(1, 1), (2, None)]
    assert "ix_old_playlist_items_position" in {row[1] for row in db.execute("PRAGMA index_list(playlist_items)")}
    assert db.execute("PRAGMA foreign_key_check").fetchall() == []


def test_deletes_follow_the_rules_once_keys_are_enforced(tmp_path):
    path = tmp_path / "ancienne.db"
    _old_schema(path)
    engine = _engine(path)
    align_foreign_keys(engine)

    with engine.begin() as conn:
        conn.exec_driver_sql("DELETE FROM videos WHERE id = 1")
        conn.exec_driver_sql("DELETE FROM backgrounds WHERE id = 1")
        assert conn.exec_driver_sql("SELECT COUNT(*) FROM playlist_items").scalar() == 0
        assert conn.exec_driver_sql("SELECT background_id FROM audio_courses WHERE id = 1").scalar() is None


def test_alignment_is_idempotent(tmp_path):
    path = tmp_path / "ancienne.db"
    _old_schema(path)
    engine = _engine(path)
    align_foreign_keys(engine)
    before = sqlite3.connect(path).execute("SELECT sql FROM sqlite_master ORDER BY name").fetchall()
    align_foreign_keys(engine)
    assert sqlite3.connect(path).execute("SELECT sql FROM sqlite_master ORDER BY name").fetchall() == before
