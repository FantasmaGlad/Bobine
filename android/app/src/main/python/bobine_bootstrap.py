"""Démarrage minimal du backend réel, pour la validation du Lot 2 (cf.
docs/plan-implementation-android.md) : import de `app.main` (le vrai backend,
mis en scène par la tâche Gradle `stagePythonSources`) et lancement d'uvicorn
dans un thread. Remplacé par un vrai `ForegroundService` au Lot 6 — ceci ne
gère ni la persistance après fermeture de l'app, ni le multi-écran.
"""

import threading

_started = False
_lock = threading.Lock()


def start_server_once(external_files_dir=None, native_library_dir=None):
    """`external_files_dir` : `context.getExternalFilesDir(null)` cote
    Kotlin (Lot 9) - pose `BOBINE_ANDROID_DATA_DIR` AVANT le premier import
    de `app.config` (transitif via `app.main`), seul moment ou ça compte
    puisque `DATA_ROOT` y est calculé une fois au niveau module.

    `native_library_dir` : `context.applicationInfo.nativeLibraryDir` cote
    Kotlin (Lot 8) - Android 10+ interdit d'executer un binaire natif
    depuis ailleurs que ce dossier (contrainte W^X). Pose
    BOBINE_FFMPEG_BIN/BOBINE_FFPROBE_BIN vers les binaires statiques ARM64
    embarques en lib*.so, UNIQUEMENT s'ils existent reellement (absents
    d'un build local sans l'etape de recuperation CI, cf. Decouvertes du
    Lot 8) - sinon app.utils.ffmpeg_binaries retombe sur les noms nus."""
    global _started
    with _lock:
        if _started:
            return
        _started = True

    def _run():
        import os
        if external_files_dir:
            os.environ["BOBINE_ANDROID_DATA_DIR"] = external_files_dir
        if native_library_dir:
            ffmpeg_path = os.path.join(native_library_dir, "libffmpeg.so")
            ffprobe_path = os.path.join(native_library_dir, "libffprobe.so")
            if os.path.exists(ffmpeg_path):
                os.environ["BOBINE_FFMPEG_BIN"] = ffmpeg_path
            if os.path.exists(ffprobe_path):
                os.environ["BOBINE_FFPROBE_BIN"] = ffprobe_path

        import uvicorn
        from app.main import app

        uvicorn.run(app, host="0.0.0.0", port=8000, workers=1)

    threading.Thread(target=_run, daemon=True).start()
