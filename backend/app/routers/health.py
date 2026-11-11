"""Contrôle de santé et heure du serveur : routes lues par le chien de garde et par les écrans."""

import time

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.database import SessionLocal
from app.utils.android_runtime import is_android
from app.utils.health import kiosk_process_alive

router = APIRouter()

_IS_ANDROID = is_android()


@router.get("/api/health")
async def health():
    """Contrôle de santé lisible par machine, consommé par le chien de garde
    `bobine-watchdog` (redémarrage auto d'un composant mort) et par toute
    supervision externe. Vérifie la dépendance critique du backend — la base
    **SQLite** — plus, à titre indicatif, la présence du **kiosque Chromium**.
    Renvoie HTTP 200 si la base répond, sinon 503. L'état du kiosque n'influe
    PAS sur le code HTTP : c'est un composant séparé, que le chien de garde
    redémarre indépendamment du backend."""
    components: dict[str, str] = {}

    def _check_database() -> str:
        try:
            db = SessionLocal()
            try:
                db.execute(text("SELECT 1"))
            finally:
                db.close()
            return "ok"
        except Exception:
            return "down"

    # `SELECT 1` synchrone
    # sorti de la boucle d'évènements — appelé toutes les 30s par le
    # watchdog systemd sur les profils desktop, et potentiellement par une
    # supervision externe sur Android, il ne doit jamais retarder les autres
    # requêtes en vol.
    components["database"] = await run_in_threadpool(_check_database)

    # `kiosk_process_alive()` énumère TOUS les processus du système
    # (`psutil.process_iter`) — non pertinent sur Android (aucun kiosque
    # Chromium à détecter, cf. `app/utils/health.py`) et
    # coûteux sous SELinux Android (chaque `/proc/<pid>` refusé lève une
    # exception interceptée)..
    components["kiosk"] = "n/a" if _IS_ANDROID else await run_in_threadpool(kiosk_process_alive)

    healthy = components["database"] == "ok"
    payload = {"status": "ok" if healthy else "degraded", "components": components}
    if not healthy:
        return JSONResponse(status_code=503, content=payload)
    return payload


@router.get("/api/time")
def get_server_time():
    """Retourne l'heure serveur en millisecondes Unix.

    Utilisé par les kiosks clients pour corriger la dérive d'horloge locale :
    le kiosk calcule delta = server_ts - Date.now() et applique ce décalage
    à tous ses affichages de l'heure.
    La précision réseau LAN (~0.5 ms) est largement suffisante pour un affichage
    à la seconde.
    """
    return {"server_ts": int(time.time() * 1000)}
