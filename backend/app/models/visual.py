"""Visuels diffusés en boucle sur un canal (images, GIF, vidéos courtes), distincts des fonds animés du coach."""

from __future__ import annotations

from .base import Base, UidMixin, VisualAssetMixin


class Visual(UidMixin, VisualAssetMixin, Base):
    __uid_prefix__ = "vis"
    __tablename__ = "visuals"
