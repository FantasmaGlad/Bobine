"""API du module Radio : sorties, bibliothèque musicale et catalogue."""

from fastapi import APIRouter

from . import catalog, outputs, tracks, uploads

router = APIRouter()

for module in (outputs, tracks, uploads, catalog):
    router.include_router(module.router, prefix="/api/radio", tags=["radio"])
