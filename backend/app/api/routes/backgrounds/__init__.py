"""API des fonds animés du coach : bibliothèque, envois et flux (routes communes des espaces visuels)."""

from app.media_assets.registry import BACKGROUNDS
from app.media_assets.routes import asset_router

router = asset_router(BACKGROUNDS)
