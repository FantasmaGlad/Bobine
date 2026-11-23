"""API des visuels diffusés en boucle : bibliothèque, envois et flux (routes communes des espaces visuels)."""

from app.media_assets.registry import VISUALS
from app.media_assets.routes import asset_router

router = asset_router(VISUALS)
