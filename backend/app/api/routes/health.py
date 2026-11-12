"""Contrôle de santé et heure du serveur : routes lues par le chien de garde et par les écrans."""

import time

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.database import SessionLocal
from app.utils.android_runtime import is_android
from app.api.static_files import frontend_out
from app.scheduling.jobs import scheduler_running
from app.utils.health import kiosk_process_alive
from app.utils.version import get_app_version

router = APIRouter()

_IS_ANDROID = is_android()


@router.get("/api/health")
async def health():
    """Contrôle de santé lisible par machine, consommé par le chien de garde `bobine-watchdog` (redémarrage auto d'un composant mort) et par toute supervision externe."""
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

    components["database"] = await run_in_threadpool(_check_database)

    components["kiosk"] = "n/a" if _IS_ANDROID else await run_in_threadpool(kiosk_process_alive)

    components["scheduler"] = "ok" if scheduler_running() else "down"
    components["frontend"] = "ok" if frontend_out.is_dir() else "missing"

    healthy = components["database"] == "ok"
    payload = {"status": "ok" if healthy else "degraded", "version": get_app_version(), "components": components}
    if not healthy:
        return JSONResponse(status_code=503, content=payload)
    return payload


@router.get("/api/time")
def get_server_time():
    """Retourne l'heure serveur en millisecondes Unix."""
    return {"server_ts": int(time.time() * 1000)}
