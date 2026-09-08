"""Démarrage minimal du backend réel, pour la validation du Lot 2 (cf.
docs/plan-implementation-android.md) : import de `app.main` (le vrai backend,
mis en scène par la tâche Gradle `stagePythonSources`) et lancement d'uvicorn
dans un thread. Remplacé par un vrai `ForegroundService` au Lot 6 — ceci ne
gère ni la persistance après fermeture de l'app, ni le multi-écran.
"""

import threading

_started = False
_lock = threading.Lock()


def start_server_once():
    global _started
    with _lock:
        if _started:
            return
        _started = True

    def _run():
        import uvicorn
        from app.main import app

        uvicorn.run(app, host="0.0.0.0", port=8000, workers=1)

    threading.Thread(target=_run, daemon=True).start()
