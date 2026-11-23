"""Sorties de diffusion : état, mode affiché et commandes de lecture et de radio de chaque sortie."""

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.contract import PLAYBACK_ACTIONS, RADIO_ACTIONS
from app.api.responses import OutputState
from app.api.routes.playback.commands import execute_command
from app.api.routes.playback.core import CommandRejected
from app.api.routes.settings.display import apply_display_output, get_display_output_value
from app.database import get_db
from app.outputs import OUTPUTS, Output, get_output
from app.playback.manager import get_playback_manager
from app.radio.manager import get_radio_manager

router = APIRouter(prefix="/api/outputs", tags=["outputs"])


class ModeUpdate(BaseModel):
    mode: str


def _unknown(kind: str, value: str, allowed) -> HTTPException:
    message = {"output": "Sortie inconnue", "action": "Action inconnue"}[kind]
    return HTTPException(status_code=404, detail={"code": f"unknown_{kind}", "message": f"{message} : {value}.", "allowed": list(allowed)})


def _output(output_id: str) -> Output:
    output = get_output(output_id)
    if output is None:
        raise _unknown("output", output_id, [o.id for o in OUTPUTS])
    return output


def _state(db: Session, output: Output) -> dict[str, Any]:
    return {
        "id": output.id, "label": output.label, "wired": output.wired, "coach": output.coach, "modes": list(output.modes),
        "mode": get_display_output_value(db, output.id),
        "playback": get_playback_manager(output.id).snapshot(), "radio": get_radio_manager(output.radio_channel).snapshot(),
    }


@router.get("", response_model=list[OutputState])
def list_outputs(db: Session = Depends(get_db)):
    """Chaque sortie avec son mode affiché, l'état de sa lecture et celui de sa radio."""
    return [_state(db, output) for output in OUTPUTS]


@router.get("/{output_id}", response_model=OutputState)
def get_output_state(output_id: str, db: Session = Depends(get_db)):
    return _state(db, _output(output_id))


@router.put("/{output_id}/mode", response_model=OutputState)
async def set_output_mode(output_id: str, payload: ModeUpdate, db: Session = Depends(get_db)):
    """Bascule le mode affiché d'une sortie (kiosque, cinéma, radio, visuel), sans toucher aux autres."""
    output = _output(output_id)
    if payload.mode not in output.modes:
        raise HTTPException(status_code=422, detail=f"Mode invalide (attendu {' ou '.join(repr(m) for m in output.modes)})")
    await apply_display_output(db, output.id, payload.mode)
    return _state(db, output)


async def _command(db: Session, output: Output, action: str, params: dict[str, Any] | None, channel: str) -> dict[str, Any]:
    try:
        await execute_command({"command": action, "params": {**(params or {}), "channel": channel}}, db)
    except CommandRejected as rejected:
        headers = {"Retry-After": "30"} if rejected.status == 503 else None
        raise HTTPException(
            status_code=rejected.status, headers=headers,
            detail={"code": rejected.reason, "message": rejected.message, "command": action, "channel": rejected.channel},
        ) from rejected
    return _state(db, output)


@router.post("/{output_id}/playback/{action}", response_model=OutputState)
async def playback_action(output_id: str, action: str, params: dict[str, Any] | None = Body(default=None), db: Session = Depends(get_db)):
    """Commande de lecture d'une sortie ; corps JSON : les paramètres de la commande WebSocket."""
    output = _output(output_id)
    if action not in PLAYBACK_ACTIONS:
        raise _unknown("action", action, PLAYBACK_ACTIONS)
    return await _command(db, output, action, params, output.id)


@router.post("/{output_id}/radio/{action}", response_model=OutputState)
async def radio_action(output_id: str, action: str, params: dict[str, Any] | None = Body(default=None), db: Session = Depends(get_db)):
    """Commande de la radio d'une sortie ; même contrat que la lecture."""
    output = _output(output_id)
    if action not in RADIO_ACTIONS:
        raise _unknown("action", action, RADIO_ACTIONS)
    return await _command(db, output, action, params, output.radio_channel)
