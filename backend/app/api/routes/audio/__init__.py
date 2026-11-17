"""API des cours audio : cours, pistes et envois."""

from fastapi import APIRouter

from . import courses, tracks, uploads

router = APIRouter()

for module in (courses, tracks, uploads,):
    router.include_router(module.router, prefix="/api/audio", tags=["audio"])
