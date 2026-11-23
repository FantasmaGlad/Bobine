"""Sortie affichée par canal (kiosque, cinéma, radio) et diffusion du mode d'affichage aux écrans."""

import logging

from fastapi import (
    Depends,
    HTTPException,
)
from sqlalchemy.orm import Session

from app.api.contract import CHANNELS, DISPLAY_OUTPUTS_BY_CHANNEL, LOCKED_OUTPUTS
from app.database import get_db
from app.models import Setting
from app.outputs import OUTPUTS, WIRED_OUTPUT, get_output
from app.playback.manager import get_playback_manager
from app.radio.manager import get_radio_manager
from app.scheduling.radio import activate_radio_output
from app.utils.activity_log import log_activity
from app.utils.deployment import (
    get_deployment_profile,
)
from app.utils.ws_manager import manager as ws_manager

from .core import _DISPLAY_OUTPUT_KEYS, DisplayOutputUpdate, _get_db_value, router
from .values import get_settings
from .wired_mode import get_effective_wired_display_mode

logger = logging.getLogger(__name__)


async def broadcast_display_mode(db: Session) -> str:
    """Diffuse le mode effectif à tous les écrans (frontend : `settings_change` et `display_mode_change`, déjà consommés par AppSettingsContext)."""
    snapshot = get_settings(db)
    mode = snapshot["wired_display_mode"]
    await ws_manager.broadcast({
        "event": "settings_change",
        "theme": snapshot["theme"],
        "theme_mode": snapshot["theme_mode"],
        "language": snapshot["language"],
        "has_custom_logo": snapshot["has_custom_logo"],
        "active_logo": snapshot["active_logo"],
        "wired_display_mode": mode,
    })
    await ws_manager.broadcast({"event": "display_mode_change", "channel": WIRED_OUTPUT.id, "mode": mode})
    return mode


def get_display_output_value(db: Session, channel: str = WIRED_OUTPUT.id) -> str:
    """Valeur de sortie active pour un canal, réutilisable hors endpoint (verrouillage cinéma dans api/routes/playback/)."""
    value = _get_db_value(db, _DISPLAY_OUTPUT_KEYS[channel])
    if value in DISPLAY_OUTPUTS_BY_CHANNEL[channel]:
        return value
    if get_output(channel).wired:
        if get_deployment_profile() == "android" or get_effective_wired_display_mode(db) == "dual_screen":
            return "cinema"
    return "kiosk"


@router.get("/display-output")
def get_display_output(db: Session = Depends(get_db)) -> dict[str, str]:
    """Sortie active des deux canaux : câblé (écran branché à la machine) et réseau (tout autre appareil du LAN)."""
    return _display_outputs(db)


def _display_outputs(db: Session) -> dict[str, str]:
    return {output.id: get_display_output_value(db, output.id) for output in OUTPUTS}


@router.put("/display-output")
async def set_display_output(payload: DisplayOutputUpdate, db: Session = Depends(get_db)) -> dict[str, str]:
    """Bascule la sortie d'un canal (câblé ou réseau), indépendamment de l'autre."""
    if payload.channel not in CHANNELS:
        expected = " ou ".join(f"'{c}'" for c in CHANNELS)
        raise HTTPException(status_code=422, detail=f"Canal invalide (attendu {expected})")
    if payload.output not in DISPLAY_OUTPUTS_BY_CHANNEL[payload.channel]:
        allowed = " ou ".join(f"'{o}'" for o in DISPLAY_OUTPUTS_BY_CHANNEL[payload.channel])
        raise HTTPException(status_code=422, detail=f"Sortie invalide pour ce canal (attendu {allowed})")

    await apply_display_output(db, payload.channel, payload.output)
    return _display_outputs(db)


async def apply_display_output(db: Session, channel: str, output: str, *, activate_radio: bool = True) -> None:
    """Applique une bascule de sortie DÉJÀ validée : persistance, arrêt de ce qui jouait sur le canal, reprise ou pause du moteur radio câblé, diffusion aux clients."""
    previous_output = get_display_output_value(db, channel)
    key = _DISPLAY_OUTPUT_KEYS[channel]
    row = db.query(Setting).filter(Setting.key == key).first()
    if row:
        row.value = output
    else:
        db.add(Setting(key=key, value=output))
    db.commit()
    from app import config_mirror

    config_mirror.schedule_mirror()

    if output in LOCKED_OUTPUTS:
        manager = get_playback_manager(channel)
        current = manager.snapshot()
        if current["current_video"] or current["current_background"] or current["current_audio_course"]:
            title = (
                (current["current_video"] or {}).get("title")
                or (current["current_background"] or {}).get("title")
                or (current["current_audio_course"] or {}).get("title")
            )
            log_activity(db, "playback_stopped", title)
        await manager.stop()

    spec = get_output(channel)
    if "radio" in spec.modes:
        if output == "radio":
            if activate_radio:
                await activate_radio_output(db, spec.radio_channel)
        elif previous_output == "radio":
            await get_radio_manager(spec.radio_channel).pause()

    await ws_manager.broadcast({"event": "display_output", "channel": channel, "output": output})
    logger.info(f"Sortie {channel} basculée sur /{output}")
