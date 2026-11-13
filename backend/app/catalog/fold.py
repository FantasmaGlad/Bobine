from __future__ import annotations

import unicodedata


def fold(text: str | None) -> str:
    decomposed = unicodedata.normalize("NFD", (text or "").casefold())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))
