"""API des cours audio : cours, pistes, envois et flux."""

from fastapi import APIRouter

from . import courses, streams, tracks, uploads

router = APIRouter()

for module in (courses, tracks, uploads,):
    router.include_router(module.router, prefix="/api/audio", tags=["audio"])
router.include_router(streams.router)
