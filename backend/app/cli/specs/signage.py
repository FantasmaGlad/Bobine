from __future__ import annotations

from typing import Any

from app.api.contract import CHANNELS, DEFAULT_CHANNEL

from .model import Arg, Call, Spec, UsageError
from .route import route

_CHANNEL = Arg(("--channel",), "canal", choices=CHANNELS, default=DEFAULT_CHANNEL)


def _table(payload: Any, _args: Any) -> str:
    rows = [f"{entry['background_id']}  {entry['play_seconds'] or 'vidéo entière'}{' s' if entry['play_seconds'] else ''}"
            f"  {entry['title']}" for entry in payload.get("items", [])]
    return "\n".join(rows) or "Boucle vide."


def _item(raw: str) -> dict:
    background, _, seconds = raw.partition(":")
    try:
        return {"background_id": int(background), "seconds": int(seconds) if seconds else None}
    except ValueError as exc:
        raise UsageError(f"élément attendu : ID ou ID:SECONDES ({raw!r})") from exc


SPECS: tuple[Spec, ...] = (
    route("signage", "list", "GET", "/api/signage", "boucle de visuels diffusée sur un canal",
          query=(f"channel={'|'.join(CHANNELS)}",), human=_table),
    Spec("signage", "set", "remplacer la boucle de visuels d'un canal (fonds, dans l'ordre)",
         lambda _client, args: Call("PUT", "/api/signage", {"channel": args.channel, "items": [_item(raw) for raw in args.items]}),
         ("PUT /api/signage",),
         (Arg(("items",), "ID ou ID:SECONDES (sans durée : 10 s pour une image, la vidéo entière)", nargs="+"), _CHANNEL),
         _table),
    Spec("signage", "clear", "vider la boucle de visuels d'un canal",
         lambda _client, args: Call("PUT", "/api/signage", {"channel": args.channel, "items": []}),
         ("PUT /api/signage",), (_CHANNEL,), _table, confirm="Vider la boucle de visuels ?"),
)
