"""API des vidéos : envois, bibliothèque, sous-titres et flux (logique dans app/videos/)."""

from fastapi import APIRouter

from . import library, storyboard, streams, subtitles, uploads

router = APIRouter()

for module in (uploads, library, subtitles, storyboard):
    router.include_router(module.router, prefix="/api/videos", tags=["videos"])
router.include_router(streams.router)
