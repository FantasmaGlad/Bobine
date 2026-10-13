"""État des écrans externes (plan 4.0, P1-1).

Chaque plateforme (service Android, tray desktop, hotplug du Wyse) remonte ici
le nombre d'écrans externes réellement connectés ; le mode d'affichage câblé
effectif (`dual_screen`/`headless`) en est dérivé et diffusé à tous les écrans
sans rechargement. Endpoint idempotent et tolérant : un rapport identique est
accepté sans effet, et ne lève jamais d'erreur serveur (règle d'or §1.2).
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers.settings import (
    broadcast_display_mode,
    get_display_mode_setting,
    get_effective_wired_display_mode,
)
from app.utils.display_state import get_hardware_state, report_external_displays

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/display", tags=["display"])


class DisplayStateReport(BaseModel):
    external_count: int = Field(ge=0, le=16, description="Nombre d'écrans externes (projecteur, TV) connectés")
    source: str | None = Field(default=None, max_length=32)
    resolution: str | None = Field(default=None, max_length=32)


def _payload(db: Session) -> dict[str, Any]:
    hw = get_hardware_state()
    return {
        "external_count": hw.external_count,
        "source": hw.source,
        "resolution": hw.resolution,
        "updated_at": hw.updated_at,
        "display_mode_setting": get_display_mode_setting(db),
        "wired_display_mode": get_effective_wired_display_mode(db),
    }


@router.get("/state")
def get_display_state(db: Session = Depends(get_db)) -> dict[str, Any]:
    return _payload(db)


@router.put("/state")
async def put_display_state(report: DisplayStateReport, db: Session = Depends(get_db)) -> dict[str, Any]:
    mode_before = get_effective_wired_display_mode(db)
    changed = report_external_displays(report.external_count, report.source, report.resolution)
    mode_after = get_effective_wired_display_mode(db)
    if changed:
        logger.info(
            f"Écrans externes : {report.external_count} (source={report.source}) — "
            f"mode effectif {mode_before} -> {mode_after}"
        )
    # On ne diffuse que si le mode EFFECTIF a bougé : un rapport identique
    # (ré-émission périodique, reconnexion du rapporteur) ne doit générer
    # aucun trafic WebSocket.
    if mode_after != mode_before:
        await broadcast_display_mode(db)
    return _payload(db)
