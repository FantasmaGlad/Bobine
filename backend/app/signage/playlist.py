"""Boucle de visuels : validation des éléments, sans base ni réseau."""

from __future__ import annotations

from dataclasses import dataclass

MAX_ITEMS = 100
MIN_SECONDS = 2
MAX_SECONDS = 3600
DEFAULT_IMAGE_SECONDS = 10


@dataclass(frozen=True)
class SignageItem:
    visual_id: int
    seconds: int | None


def check_item(raw: object) -> SignageItem:
    if not isinstance(raw, dict):
        raise ValueError("élément : objet {visual_id, seconds}")
    visual_id = raw.get("visual_id")
    if isinstance(visual_id, bool) or not isinstance(visual_id, int) or visual_id < 1:
        raise ValueError("visual_id : entier positif")
    seconds = raw.get("seconds")
    if seconds is not None and (isinstance(seconds, bool) or not isinstance(seconds, int)
                                or not MIN_SECONDS <= seconds <= MAX_SECONDS):
        raise ValueError(f"seconds : entier de {MIN_SECONDS} à {MAX_SECONDS}, ou null pour la durée de la vidéo")
    return SignageItem(visual_id, seconds)


def parse_items(raw: object) -> tuple[SignageItem, ...]:
    """Une liste abîmée est refusée en entier."""
    if not isinstance(raw, list) or len(raw) > MAX_ITEMS:
        raise ValueError(f"éléments : liste de {MAX_ITEMS} au plus")
    return tuple(check_item(item) for item in raw)


def resolved_seconds(item: SignageItem, is_image: bool) -> int | None:
    """Durée d'affichage : celle choisie, sinon 10 s pour une image et la vidéo entière pour une vidéo."""
    if item.seconds is not None:
        return item.seconds
    return DEFAULT_IMAGE_SECONDS if is_image else None


def serialize(items: tuple[SignageItem, ...]) -> list[dict]:
    return [{"visual_id": item.visual_id, "seconds": item.seconds} for item in items]
