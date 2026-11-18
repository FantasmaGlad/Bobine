"""Maintien de l'activité capot fermé sur un ordinateur portable."""

from fastapi import HTTPException
from pydantic import BaseModel

from app.api.responses import LaptopLid
from app.hardware import lid

from .core import router


class LaptopLidPayload(BaseModel):
    prevent_sleep: bool


@router.get("/laptop-lid", response_model=LaptopLid)
def get_laptop_lid():
    """Vérifie si la machine a un capot et renvoie le réglage actuel."""
    has_lid = lid.has_lid()
    prevent = lid.prevent_sleep() if has_lid else False
    return {"has_lid": has_lid, "prevent_sleep": prevent}


@router.post("/laptop-lid", response_model=LaptopLid)
def set_laptop_lid(payload: LaptopLidPayload):
    """Active ou désactive la mise en veille à la fermeture du capot."""
    if not lid.has_lid():
        raise HTTPException(status_code=409, detail="Aucun capot détecté sur cet appareil")
    if not lid.set_prevent_sleep(payload.prevent_sleep):
        raise HTTPException(status_code=500, detail="Impossible d'appliquer le réglage du capot")
    return {"has_lid": True, "prevent_sleep": payload.prevent_sleep}
