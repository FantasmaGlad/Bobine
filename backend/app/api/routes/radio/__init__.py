"""API du module Radio : sorties, bibliothèque musicale, catalogue et flux."""

from fastapi import APIRouter

from . import catalog, outputs, streams, tracks, uploads

router = APIRouter()

for module in (outputs, tracks, uploads, catalog):
    router.include_router(module.router, prefix="/api/radio", tags=["radio"])
router.include_router(streams.router)
