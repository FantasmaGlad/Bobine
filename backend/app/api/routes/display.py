"""État des écrans externes."""

import logging
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.routes.settings.display import broadcast_display_mode
from app.api.routes.settings.wired_mode import get_display_mode_setting, get_effective_wired_display_mode
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
    if mode_after != mode_before:
        await broadcast_display_mode(db)
    return _payload(db)
