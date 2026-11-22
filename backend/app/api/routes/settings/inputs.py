"""Correspondances entre entrées (clavier, télécommande, manette) et actions de lecture."""

from fastapi import Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.responses import RemoteInputs
from app.database import get_db
from app.inputs import store
from app.inputs.bindings import DEFAULT_BINDINGS, REMOTE_ACTIONS
from app.inputs.overrides import Overrides, effective_bindings, with_override
from app.utils.ws_manager import manager as ws_manager

from .core import router


class InputPatch(BaseModel):
    input: str
    actions: list[str] | None = None


def _payload(overrides: Overrides) -> dict:
    return {
        "actions": list(REMOTE_ACTIONS),
        "defaults": {source: list(actions) for source, actions in DEFAULT_BINDINGS.items()},
        "overrides": {source: list(actions) for source, actions in overrides.items()},
        "bindings": effective_bindings(overrides),
    }


async def _publish(db: Session, overrides: Overrides) -> dict:
    store.save(db, overrides)
    await ws_manager.broadcast({"event": "inputs_change", "bindings": effective_bindings(overrides)})
    return _payload(overrides)


@router.get("/inputs", response_model=RemoteInputs)
def get_inputs(db: Session = Depends(get_db)):
    """Actions, table par défaut, correspondances choisies et table appliquée."""
    return _payload(store.load(db))


@router.patch("/inputs", response_model=RemoteInputs)
async def patch_input(payload: InputPatch, db: Session = Depends(get_db)):
    """Associe une entrée à des actions par ordre de préférence ; liste vide : entrée désactivée ; `null` : valeur par défaut."""
    try:
        overrides = with_override(store.load(db), payload.input, payload.actions)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return await _publish(db, overrides)


@router.delete("/inputs", response_model=RemoteInputs)
async def reset_inputs(db: Session = Depends(get_db)):
    """Rend toutes les entrées à la table par défaut."""
    return await _publish(db, {})
