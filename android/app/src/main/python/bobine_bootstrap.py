"""Démarrage du backend réel : import de `app.main` (le vrai backend, mis en scène par la tâche Gradle `stagePythonSources`) et lancement d'uvicorn dans un thread."""

import os
import shutil
import sqlite3
import threading

os.environ["BOBINE_PLATFORM"] = "android"

_started = False
_lock = threading.Lock()

_MIGRATED_DB_RELATIVE = "data/database.db"
_MIGRATED_DIRS_RELATIVE = ("data/thumbnails", "data/logs", "data/branding", "data/radio_covers")


def _checkpoint_and_copy_database(external_data_dir, internal_data_dir):
    external_db = os.path.join(external_data_dir, _MIGRATED_DB_RELATIVE)
    internal_db = os.path.join(internal_data_dir, _MIGRATED_DB_RELATIVE)
    if not os.path.exists(external_db) or os.path.exists(internal_db):
        return False

    os.makedirs(os.path.dirname(internal_db), exist_ok=True)
    try:
        conn = sqlite3.connect(external_db, timeout=30)
        try:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.commit()
        finally:
            conn.close()

        shutil.copy2(external_db, internal_db)

        old_thumb_dir = os.path.join(external_data_dir, "data/thumbnails")
        new_thumb_dir = os.path.join(internal_data_dir, "data/thumbnails")
        old_cover_dir = os.path.join(external_data_dir, "data/radio_covers")
        new_cover_dir = os.path.join(internal_data_dir, "data/radio_covers")
        conn = sqlite3.connect(internal_db, timeout=30)
        try:
            conn.execute(
                "UPDATE videos SET thumbnail_path = replace(thumbnail_path, ?, ?) "
                "WHERE thumbnail_path IS NOT NULL",
                (old_thumb_dir, new_thumb_dir),
            )
            conn.execute(
                "UPDATE radio_tracks SET cover_path = replace(cover_path, ?, ?) "
                "WHERE cover_path IS NOT NULL",
                (old_cover_dir, new_cover_dir),
            )
            integrity = conn.execute("PRAGMA integrity_check").fetchone()
            conn.commit()
        finally:
            conn.close()

        if not integrity or integrity[0] != "ok":
            os.remove(internal_db)
            return False
        return True
    except Exception:
        try:
            if os.path.exists(internal_db):
                os.remove(internal_db)
        except Exception:
            pass
        return False


def _migrate_small_dirs(external_data_dir, internal_data_dir):
    for rel_dir in _MIGRATED_DIRS_RELATIVE:
        src = os.path.join(external_data_dir, rel_dir)
        dst = os.path.join(internal_data_dir, rel_dir)
        if not os.path.isdir(src) or os.path.isdir(dst):
            continue
        try:
            shutil.copytree(src, dst)
        except Exception:
            pass


def _migrate_to_internal_storage_once(external_files_dir, internal_files_dir):
    if not external_files_dir or not internal_files_dir:
        return
    external_data_dir = os.path.join(external_files_dir)
    internal_data_dir = os.path.join(internal_files_dir)
    if _checkpoint_and_copy_database(external_data_dir, internal_data_dir):
        _migrate_small_dirs(external_data_dir, internal_data_dir)


def start_server_once(external_files_dir=None, native_library_dir=None, internal_files_dir=None, app_version=None):
    """`external_files_dir` : `context.getExternalFilesDir(null)` côté Kotlin — médias uniquement."""
    global _started
    with _lock:
        if _started:
            return
        _started = True

    def _run():
        import os as _os
        if app_version:
            _os.environ["BOBINE_VERSION"] = str(app_version)
        if external_files_dir:
            _os.environ["BOBINE_ANDROID_DATA_DIR"] = external_files_dir
        if internal_files_dir:
            _os.environ["BOBINE_ANDROID_INTERNAL_DIR"] = internal_files_dir
            if external_files_dir:
                _migrate_to_internal_storage_once(external_files_dir, internal_files_dir)
        if native_library_dir:
            ffmpeg_path = _os.path.join(native_library_dir, "libffmpeg.so")
            ffprobe_path = _os.path.join(native_library_dir, "libffprobe.so")
            media_path = _os.path.join(native_library_dir, "libbobine_media.so")
            if _os.path.exists(ffmpeg_path):
                _os.environ["BOBINE_FFMPEG_BIN"] = ffmpeg_path
            if _os.path.exists(ffprobe_path):
                _os.environ["BOBINE_FFPROBE_BIN"] = ffprobe_path
            if _os.path.isfile(media_path) and _os.access(media_path, _os.X_OK):
                _os.environ["BOBINE_MEDIA_BIN"] = media_path

        import uvicorn
        from app.config import settings
        from app.main import app
        from app.utils.port import acquire_listen_port, release_port

        listen_port = acquire_listen_port()

        try:
            uvicorn.run(
                app, host=settings.host, port=listen_port, workers=1,
                timeout_keep_alive=75, ws_ping_interval=None, ws_ping_timeout=None,
                limit_concurrency=64, proxy_headers=False,
            )
        finally:
            release_port()

    threading.Thread(target=_run, daemon=True).start()
