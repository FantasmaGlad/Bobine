"""Démarrage minimal du backend réel, pour la validation du Lot 2 (cf.
docs/plan-implementation-android.md) : import de `app.main` (le vrai backend,
mis en scène par la tâche Gradle `stagePythonSources`) et lancement d'uvicorn
dans un thread. Remplacé par un vrai `ForegroundService` au Lot 6 — ceci ne
gère ni la persistance après fermeture de l'app, ni le multi-écran.
"""

import threading

_started = False
_lock = threading.Lock()


def start_server_once(external_files_dir=None):
    """`external_files_dir` : `context.getExternalFilesDir(null)` cote
    Kotlin (Lot 9) - pose `BOBINE_ANDROID_DATA_DIR` AVANT le premier import
    de `app.config` (transitif via `app.main`), seul moment ou ça compte
    puisque `DATA_ROOT` y est calculé une fois au niveau module."""
    global _started
    with _lock:
        if _started:
            return
        _started = True

    def _run():
        if external_files_dir:
            import os
            os.environ["BOBINE_ANDROID_DATA_DIR"] = external_files_dir

        import uvicorn
        from app.main import app

        uvicorn.run(app, host="0.0.0.0", port=8000, workers=1)

    threading.Thread(target=_run, daemon=True).start()
