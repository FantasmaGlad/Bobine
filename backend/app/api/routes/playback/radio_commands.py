"""Commandes de la radio : pistes, fins de piste, rappels vocaux."""

import logging

from fastapi import WebSocket
from sqlalchemy.orm import Session

from app.devices.service import PLAYER_ROUTE_STATUSES
from app.devices.service import service as devices_service
from app.models import (
    RadioAnnouncement,
    RadioAnnouncementRule,
    RadioAnnouncementRuleType,
    RadioPlaylist,
    RadioTrack,
)
from app.radio_manager import (
    get_radio_manager,
    rule_targets_output,
)
from app.scheduling.radio import radio_track_dict
from app.utils import radio_commands
from app.utils.activity_log import log_activity
from app.utils.radio_mix import sanitize_levels
from app.utils.ws_manager import manager as ws_manager

from .context import Command
from .core import CommandRejected, _reject_unavailable

logger = logging.getLogger(__name__)


async def _handle_radio_track_ended(manager, db, client_ts, track_id: int | None) -> None:
    current = manager.state.get("current_track")
    if track_id is not None and current is not None and current.get("id") != track_id:
        return
    manager.state["tracks_since_announcement"] = manager.state.get("tracks_since_announcement", 0) + 1
    due = _due_wait_end_announcement(db, manager)
    if due:
        await manager.play_announcement(
            {"id": due.id, "description": due.description}, mode="wait_end",
            client_ts=client_ts, deferred_advance=True,
        )
    else:
        await manager.track_ended(client_ts, track_id=track_id)


async def _radio_track_end_fallback(radio_channel: str, track_id: int | None) -> None:
    from app.database import SessionLocal

    with SessionLocal() as db:
        await _handle_radio_track_ended(get_radio_manager(radio_channel), db, None, track_id)


async def _load_radio_playlist(cmd: Command) -> None:
    playlist_id = cmd.params.get("playlist_id")
    playlist = cmd.db.query(RadioPlaylist).filter(RadioPlaylist.id == playlist_id).first()
    if not playlist:
        raise cmd.not_found(f"Playlist radio {playlist_id}")
    items = sorted(playlist.items, key=lambda item: item.position)
    tracks = [radio_track_dict(item.track) for item in items if item.track and item.track.available]
    await cmd.manager.load_playlist(playlist.id, playlist.name, tracks, shuffle=cmd.params.get("shuffle"),
                                    client_ts=cmd.client_ts, repeat="playlist")
    log_activity(cmd.db, "radio_playlist_started", playlist.name)


async def _shuffle_all(cmd: Command) -> None:
    tracks = [radio_track_dict(t) for t in cmd.db.query(RadioTrack).all() if t.available]
    if not tracks:
        logger.info("Commande radio_shuffle_all : bibliothèque radio vide")
        raise CommandRejected("empty_library", cmd.channel, "La bibliothèque radio ne contient aucun morceau disponible.")
    await cmd.manager.load_playlist(None, "Toute la bibliothèque", tracks, shuffle=True, client_ts=cmd.client_ts, repeat="playlist")
    log_activity(cmd.db, "radio_shuffle_all_started", f"{len(tracks)} morceau(x)")


async def _available_track(cmd: Command) -> dict:
    track = cmd.db.query(RadioTrack).filter(RadioTrack.id == cmd.params.get("track_id")).first()
    if not track:
        raise cmd.not_found(f"Morceau {cmd.params.get('track_id')}")
    if not track.available:
        await _reject_unavailable(cmd.name, cmd.channel, track.title, cmd.db)
    return radio_track_dict(track)


async def _add_to_queue(cmd: Command) -> None:
    await cmd.manager.add_to_queue(await _available_track(cmd), cmd.client_ts)


async def _play_next(cmd: Command) -> None:
    await cmd.manager.play_next(await _available_track(cmd), cmd.client_ts)


async def _report_route(cmd: Command) -> None:
    status = cmd.params.get("status") if cmd.params.get("status") in PLAYER_ROUTE_STATUSES else "error"
    if cmd.websocket is not None and ws_manager.set_route_report(cmd.websocket, {"status": status}):
        devices_service.note_player_report(cmd.channel)


async def _report_levels(cmd: Command) -> None:
    if cmd.websocket is not None and ws_manager.is_primary_kiosk(cmd.websocket):
        await cmd.manager.relay_levels(sanitize_levels(cmd.params.get("levels")))


async def _track_ended(cmd: Command) -> None:
    raw = cmd.params.get("track_id")
    track_id = raw if isinstance(raw, int) and not isinstance(raw, bool) else None
    await _handle_radio_track_ended(cmd.manager, cmd.db, cmd.client_ts, track_id)


async def _play_announcement(cmd: Command) -> None:
    announcement = radio_commands.resolve_announcement(cmd.db, cmd.params.get("announcement_id"))
    if not announcement:
        raise cmd.not_found("Rappel")
    await radio_commands.play_announcement_now(cmd.db, [cmd.manager], announcement, cmd.client_ts)


async def _report_position(cmd: Command) -> None:
    if not cmd.secondary_kiosk():
        await cmd.manager.report_position(float(cmd.params.get("position_seconds", 0)))


_HANDLERS = {
    "load_radio_playlist": _load_radio_playlist,
    "radio_shuffle_all": _shuffle_all,
    "radio_add_to_queue": _add_to_queue,
    "radio_play_next": _play_next,
    "radio_report_route": _report_route,
    "radio_report_levels": _report_levels,
    "radio_track_ended": _track_ended,
    "radio_play_announcement": _play_announcement,
    "report_position": _report_position,
    "play": lambda cmd: cmd.manager.play(cmd.client_ts),
    "pause": lambda cmd: cmd.manager.pause(cmd.client_ts),
    "stop": lambda cmd: cmd.manager.stop(cmd.client_ts),
    "radio_next_track": lambda cmd: cmd.manager.next_track(cmd.client_ts),
    "radio_previous_track": lambda cmd: cmd.manager.previous_track(cmd.client_ts),
    "radio_jump_to_track": lambda cmd: cmd.manager.jump_to(int(cmd.params.get("index", 0)), cmd.client_ts),
    "radio_seek": lambda cmd: cmd.manager.seek(float(cmd.params.get("position_seconds", 0)), cmd.client_ts),
    "volume": lambda cmd: cmd.manager.set_volume(cmd.params.get("volume", 100), cmd.client_ts),
    "radio_set_sound": lambda cmd: radio_commands.apply_sound(cmd.db, cmd.manager, cmd.params.get("sound"), cmd.client_ts),
    "radio_meter": lambda cmd: cmd.manager.request_meter(),
    "radio_set_shuffle": lambda cmd: cmd.manager.set_shuffle(bool(cmd.params.get("on")), cmd.client_ts),
    "radio_set_repeat": lambda cmd: cmd.manager.set_repeat(cmd.params.get("mode", "off"), cmd.client_ts),
    "radio_move_in_queue": lambda cmd: cmd.manager.move_in_order(
        int(cmd.params.get("from_index", -1)), int(cmd.params.get("to_index", -1)), cmd.client_ts),
    "radio_remove_from_queue": lambda cmd: cmd.manager.remove_from_order(int(cmd.params.get("index", -1)), cmd.client_ts),
    "announcement_ended": lambda cmd: cmd.manager.announcement_ended(cmd.client_ts),
}


async def _handle_radio_command(
    command: str, params: dict, client_ts, db: Session,
    websocket: WebSocket | None = None, is_kiosk: bool = False,
    radio_channel: str | None = None,
) -> None:
    manager = get_radio_manager(radio_channel)
    handler = _HANDLERS.get(command)
    if handler is None:
        logger.warning(f"Commande radio WebSocket inconnue reçue : {command}")
        raise CommandRejected("unknown_command", manager.channel, f"Commande radio inconnue : {command}.", 400)
    await handler(Command(command, params, client_ts, db, websocket, is_kiosk, manager.channel, manager))


def _due_wait_end_announcement(db: Session, manager) -> RadioAnnouncement | None:
    count = manager.state.get("tracks_since_announcement", 0)
    rules = (
        db.query(RadioAnnouncementRule)
        .filter(
            RadioAnnouncementRule.enabled == True,  # noqa: E712
            RadioAnnouncementRule.rule_type == RadioAnnouncementRuleType.every_n_tracks,
        )
        .all()
    )
    if not any(
        count >= (rule.n_tracks or 1) and rule_targets_output(rule.target, manager.channel) for rule in rules
    ):
        return None
    return radio_commands.resolve_announcement(db, None)
