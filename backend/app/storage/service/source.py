"""Source d'une action : racine lisible, nature et identifiant de traçabilité."""

from __future__ import annotations

from dataclasses import dataclass

from app.storage.types import Volume


@dataclass
class Source:
    """Ce qu'une action doit savoir d'une source : racine lisible, nature, identifiant de traçabilité."""

    key: str
    root: str
    portable: bool
    volume: Volume | None
    source_id: str
