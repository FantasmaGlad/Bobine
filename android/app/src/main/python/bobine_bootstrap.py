"""Démarrage du backend réel : import de `app.main` (le vrai backend, mis en
scène par la tâche Gradle `stagePythonSources`) et lancement d'uvicorn dans
un thread. Appelé par `BobineForegroundService.kt`.

Lot 15 (docs/audit-android-2026-09-11.md §C1/C3, réf. plan-implementation-
android.md) : reçoit désormais DEUX racines de stockage, pas une seule.
- `internal_files_dir` (`context.filesDir` côté Kotlin) : stockage privé de
  l'app sur `/data`, f2fs natif, jamais servi par FUSE — utilisé pour la
  base SQLite, les miniatures, les logs, le branding et les pochettes radio
  (petits fichiers à I/O aléatoire fréquente, très sensibles à FUSE).
- `external_files_dir` (`context.getExternalFilesDir(null)`) : stockage
  externe spécifique à l'app, persiste entre mises à jour, visible via un
  gestionnaire de fichiers/MTP, servi par FUSE — reste utilisé pour les
  médias (vidéos, fonds, audio, radio : gros fichiers lus par blocs
  séquentiels, coût FUSE par octet négligeable, contrairement à la base).

Avant Lot 15, la base SQLite vivait sur le stockage externe (FUSE) — cause
racine mesurée de la lenteur/non-réponse réseau (docs/audit-android-2026-09-11.md
§4 : chaque écriture SQLite bloquant sur FUSE ralentit toute la boucle
d'évènements, jusqu'à `PRAGMA busy_timeout=30000`). Ce module migre une
installation existante UNE SEULE FOIS, avant tout import de `app.config`
(la seule fenêtre où poser les variables d'environnement compte, cf.
`config.py::DATA_ROOT`/`_android_internal_root()` calculés une fois au
niveau module).
"""

import os
import shutil
import sqlite3
import threading

_started = False
_lock = threading.Lock()

# Sous-chemins par défaut de backend/app/config.py::Settings — dupliqués ici
# à dessein (pas d'import de app.config avant que les variables
# d'environnement de ce module ne soient posées, sous peine de figer
# DATA_ROOT sur la mauvaise racine pour toute la durée du process). Garder
# synchronisé avec les valeurs par défaut de la classe Settings si elles
# changent un jour.
_MIGRATED_DB_RELATIVE = "data/database.db"
_MIGRATED_DIRS_RELATIVE = ("data/thumbnails", "data/logs", "data/branding", "data/radio_covers")


def _checkpoint_and_copy_database(external_data_dir, internal_data_dir):
    """Copie `data/database.db` (+ -wal/-shm) de l'externe vers l'interne,
    avec vérification d'intégrité AVANT toute utilisation — ne supprime
    JAMAIS l'original (même philosophie que
    `backend/app/utils/importer.py::reconcile_orphaned_media` : un
    diagnostic qui se trompe ne doit jamais être destructif). Retourne
    True si la copie interne est utilisable, False sinon (l'appelant
    laisse alors `app.config` créer une base neuve sur l'interne, comme
    avant ce lot pour une toute première installation)."""
    external_db = os.path.join(external_data_dir, _MIGRATED_DB_RELATIVE)
    internal_db = os.path.join(internal_data_dir, _MIGRATED_DB_RELATIVE)
    if not os.path.exists(external_db) or os.path.exists(internal_db):
        # Rien à migrer (première installation) ou déjà migré (relances
        # suivantes du service) — idempotent par construction.
        return False

    os.makedirs(os.path.dirname(internal_db), exist_ok=True)
    try:
        # Checkpoint AVANT copie : replie le contenu de -wal dans le fichier
        # principal, pour ne pas avoir à copier/recaler un -wal séparé, et
        # pour que le fichier copié soit auto-suffisant, sans dépendre d'un
        # -shm qui n'a de sens qu'attaché à un process SQLite vivant.
        conn = sqlite3.connect(external_db, timeout=30)
        try:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.commit()
        finally:
            conn.close()

        shutil.copy2(external_db, internal_db)

        # Réécriture des chemins absolus stockés en base (réf. même schéma
        # que scripts/migrate_unify_data_dirs.py) : thumbnail_path et
        # cover_path pointaient vers l'ancien dossier externe, qui ne
        # contiendra plus ces fichiers une fois les dossiers ci-dessous
        # migrés — sans cette réécriture, toutes les miniatures/pochettes
        # deviendraient introuvables (404) après la migration.
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
        # Toute erreur (verrou, espace disque, permission...) : la copie
        # interne partielle éventuelle est purgée, l'externe n'a jamais été
        # touché — repli sûr sur une base neuve côté interne, exactement le
        # comportement d'avant ce lot.
        try:
            if os.path.exists(internal_db):
                os.remove(internal_db)
        except Exception:
            pass
        return False


def _migrate_small_dirs(external_data_dir, internal_data_dir):
    """Copie (jamais déplace) les dossiers à faible volume vers l'interne.
    Best-effort et non bloquant : un échec ici (miniatures manquantes) est
    nettement moins grave qu'un échec sur la base elle-même, régénérable
    (miniatures) ou reconstructible (logs)."""
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


def start_server_once(external_files_dir=None, native_library_dir=None, internal_files_dir=None):
    """`external_files_dir` : `context.getExternalFilesDir(null)` côté
    Kotlin (Lot 9) — médias uniquement depuis le Lot 15, cf. docstring de
    module.

    `internal_files_dir` : `context.filesDir` côté Kotlin (Lot 15) — base
    SQLite, miniatures, logs, branding, pochettes radio. Optionnel pour ne
    pas casser un appelant Kotlin non mis à jour (repli intégral sur
    `external_files_dir` pour tout, comportement du Lot 9).

    `native_library_dir` : `context.applicationInfo.nativeLibraryDir` côté
    Kotlin (Lot 8) — Android 10+ interdit d'exécuter un binaire natif
    depuis ailleurs que ce dossier (contrainte W^X). Pose
    BOBINE_FFMPEG_BIN/BOBINE_FFPROBE_BIN vers les binaires statiques ARM64
    embarqués en lib*.so, UNIQUEMENT s'ils existent réellement (absents
    d'un build local sans l'étape de récupération CI, cf. Découvertes du
    Lot 8) — sinon app.utils.ffmpeg_binaries retombe sur les noms nus."""
    global _started
    with _lock:
        if _started:
            return
        _started = True

    def _run():
        import os as _os
        if external_files_dir:
            _os.environ["BOBINE_ANDROID_DATA_DIR"] = external_files_dir
        if internal_files_dir:
            _os.environ["BOBINE_ANDROID_INTERNAL_DIR"] = internal_files_dir
            if external_files_dir:
                _migrate_to_internal_storage_once(external_files_dir, internal_files_dir)
        if native_library_dir:
            ffmpeg_path = _os.path.join(native_library_dir, "libffmpeg.so")
            ffprobe_path = _os.path.join(native_library_dir, "libffprobe.so")
            if _os.path.exists(ffmpeg_path):
                _os.environ["BOBINE_FFMPEG_BIN"] = ffmpeg_path
            if _os.path.exists(ffprobe_path):
                _os.environ["BOBINE_FFPROBE_BIN"] = ffprobe_path

        import uvicorn
        from app.main import app

        # Lot 15 (docs/audit-android-2026-09-11.md §2/C2) : keepalive HTTP
        # allongé (Chromium/WebView ré-ouvrait une connexion TCP entre deux
        # requêtes Range espacées de plus de 5s, coût élevé sur ce
        # matériel) ; ping WebSocket natif d'uvicorn désactivé (le
        # keepalive applicatif de `ws_manager.py` — 30s/60s, tolérant aux
        # pages en arrière-plan — suffit, deux mécanismes de ping
        # indépendants n'apportaient rien) ; concurrence plafonnée à une
        # valeur adaptée à un usage salle (pas un service public), pour
        # limiter le nombre de tâches concurrentes sur un CPU mobile.
        uvicorn.run(
            app, host="0.0.0.0", port=8000, workers=1,
            timeout_keep_alive=75, ws_ping_interval=None, ws_ping_timeout=None,
            limit_concurrency=64,
        )

    threading.Thread(target=_run, daemon=True).start()
