"""Identifiants stables des objets de Bobine : `<préfixe>_<12 hexadécimaux>` (`vid_3f9a1c07b2de`)."""
from __future__ import annotations

import re
import uuid

PREFIXES = {
    "vid": "vidéo", "crs": "cours audio", "trk": "piste de cours", "rtk": "morceau radio", "bg": "fond",
    "pl": "playlist vidéo", "apl": "playlist audio", "rpl": "playlist radio", "tag": "étiquette radio",
    "ann": "annonce", "rul": "règle d'annonce", "sch": "programmation", "ovr": "exception de planning",
}
_UID_RE = re.compile(r"^([a-z]{2,3})_[0-9a-f]{12}$")


def new_uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def is_uid(value: object, prefix: str | None = None) -> bool:
    """Vrai pour un identifiant bien formé (du préfixe donné, le cas échéant)."""
    match = _UID_RE.match(value) if isinstance(value, str) else None
    return bool(match) and match.group(1) in PREFIXES and (prefix is None or match.group(1) == prefix)
