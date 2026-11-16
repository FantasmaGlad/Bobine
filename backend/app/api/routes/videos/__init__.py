"""API des vidéos : envois, bibliothèque et sous-titres (logique dans app/videos/)."""

from fastapi import APIRouter

from . import library, subtitles, uploads

router = APIRouter()

for module in (uploads, library, subtitles):
    router.include_router(module.router, prefix="/api/videos", tags=["videos"])
