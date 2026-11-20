"""API des fonds animés : bibliothèque, envois et flux."""

from fastapi import APIRouter

from . import library, streams

router = APIRouter()
router.include_router(library.router)
router.include_router(streams.router)
