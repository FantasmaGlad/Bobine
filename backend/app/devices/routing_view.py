"""Sorties radio : vue des routes audio et choix d'une sortie, d'un repli ou de l'effacement."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.radio_manager import RADIO_CHANNELS, get_all_radio_managers
from app.utils.ws_manager import manager as ws_manager

from . import locality
from .audio_meta import load_audio_meta, with_meta
from .base import DeviceError
from .routing import FALLBACKS, describe_sink, load_routes, resolve_route, save_routes


def _route_public(route: dict[str, Any] | None) -> dict[str, Any] | None:
    if route is None:
        return None
    return {k: route[k] for k in ("sink_id", "key", "label", "kind", "fallback")}


def _players(channel: str) -> list[dict[str, Any]]:
    return [
        {"local": locality.is_local_client(str(p["ip"])), "primary": p["primary"], "status": (p["report"] or {}).get("status")}
        for p in ws_manager.route_players(channel)
    ]


async def routing_view(service: Any, db: Session) -> dict[str, Any]:
    caps = await service.driver.capabilities()
    audio_cap = caps.get("audio_list", {"supported": False})
    sinks = await service.current_sinks()
    routes = load_routes(db)
    managers = get_all_radio_managers()
    outputs = []
    for channel in RADIO_CHANNELS:
        route = routes.get(channel)
        resolution = resolve_route(route, sinks)
        manager = managers.get(channel)
        outputs.append({
            "channel": channel,
            "route": _route_public(route),
            "state": resolution["state"],
            "sink_id": resolution["sink"]["id"] if resolution["sink"] else None,
            "playing": bool(manager and manager.state.get("playing")),
            "players": _players(channel),
            "server": service.server_status(channel),
        })
    return {
        "supported": bool(audio_cap.get("supported")),
        "reason": audio_cap.get("reason") or None,
        "server_mechanism": caps.get("audio_route_stream", {"supported": False}),
        "fallbacks": list(FALLBACKS),
        "outputs": outputs,
    }


async def _route_to_sink(service: Any, db: Session, sink_id: str, fallback: str | None, current: dict[str, Any] | None) -> dict[str, Any]:
    sinks = await service.current_sinks()
    if sinks is None:
        raise DeviceError("unsupported", "Le choix de la sortie audio n'est pas possible sur cette machine.", 501)
    entry = next((s for s in sinks if s.get("id") == sink_id), None)
    if entry is None:
        raise DeviceError("not_found", "Cette sortie audio n'est plus disponible.", 404)
    descriptor = describe_sink(with_meta(entry, load_audio_meta(db)))
    descriptor["fallback"] = fallback or (current or {}).get("fallback") or FALLBACKS[0]
    return descriptor


async def apply_route(service: Any, db: Session, channel: str, sink_id: str | None, fallback: str | None, clear: bool) -> str:
    """Enregistre le choix et rend la ligne de journal ; la route réelle est recalculée par l'appelant."""
    if channel not in RADIO_CHANNELS:
        raise DeviceError("bad_channel", "Sortie radio inconnue.", 400)
    if fallback is not None and fallback not in FALLBACKS:
        raise DeviceError("bad_fallback", "Repli inconnu.", 400)
    routes = load_routes(db)
    current = routes.get(channel)
    if clear:
        routes.pop(channel, None)
        detail = f"{channel} -> défaut"
    elif sink_id:
        routes[channel] = await _route_to_sink(service, db, sink_id, fallback, current)
        detail = f"{channel} -> {routes[channel]['label']}"
    elif fallback is not None:
        if current is None:
            raise DeviceError("no_route", "Aucune sortie n'est choisie pour cette sortie radio.", 400)
        routes[channel] = {**current, "fallback": fallback}
        detail = f"{channel} repli {fallback}"
    else:
        raise DeviceError("bad_request", "Indiquez une sortie audio, un repli ou l'effacement de la route.", 400)
    save_routes(db, routes)
    return detail
