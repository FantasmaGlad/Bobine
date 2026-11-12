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

from .core import CommandRejected, _not_found, _reject_unavailable

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


async def _handle_radio_command(
    command: str, params: dict, client_ts, db: Session,
    websocket: WebSocket | None = None, is_kiosk: bool = False,
    radio_channel: str | None = None,
) -> None:
    manager = get_radio_manager(radio_channel)

    if command == "load_radio_playlist":
        playlist_id = params.get("playlist_id")
        playlist = db.query(RadioPlaylist).filter(RadioPlaylist.id == playlist_id).first()
        if not playlist:
            raise _not_found(command, manager.channel, f"Playlist radio {playlist_id}")
        sorted_items = sorted(playlist.items, key=lambda item: item.position)
        tracks = [radio_track_dict(item.track) for item in sorted_items if item.track and item.track.available]
        await manager.load_playlist(
            playlist.id, playlist.name, tracks, shuffle=params.get("shuffle"), client_ts=client_ts,
            repeat="playlist",
        )
        log_activity(db, "radio_playlist_started", playlist.name)
    elif command == "radio_shuffle_all":
        tracks = [radio_track_dict(t) for t in db.query(RadioTrack).all() if t.available]
        if not tracks:
            logger.info("Commande radio_shuffle_all : bibliothèque radio vide")
            raise CommandRejected("empty_library", manager.channel, "La bibliothèque radio ne contient aucun morceau disponible.")
        await manager.load_playlist(
            None, "Toute la bibliothèque", tracks, shuffle=True, client_ts=client_ts, repeat="playlist",
        )
        log_activity(db, "radio_shuffle_all_started", f"{len(tracks)} morceau(x)")
    elif command == "play":
        await manager.play(client_ts)
    elif command == "pause":
        await manager.pause(client_ts)
    elif command == "stop":
        await manager.stop(client_ts)
    elif command == "radio_next_track":
        await manager.next_track(client_ts)
    elif command == "radio_previous_track":
        await manager.previous_track(client_ts)
    elif command == "radio_jump_to_track":
        await manager.jump_to(int(params.get("index", 0)), client_ts)
    elif command == "radio_seek":
        await manager.seek(float(params.get("position_seconds", 0)), client_ts)
    elif command == "volume":
        await manager.set_volume(params.get("volume", 100), client_ts)
    elif command == "radio_set_sound":
        await radio_commands.apply_sound(db, manager, params.get("sound"), client_ts)
    elif command == "radio_report_route":
        status = params.get("status") if params.get("status") in PLAYER_ROUTE_STATUSES else "error"
        if websocket is not None and ws_manager.set_route_report(websocket, {"status": status}):
            devices_service.note_player_report(manager.channel)
    elif command == "radio_meter":
        await manager.request_meter()
    elif command == "radio_report_levels":
        if websocket is None or not ws_manager.is_primary_kiosk(websocket):
            return
        await manager.relay_levels(sanitize_levels(params.get("levels")))
    elif command == "radio_set_shuffle":
        await manager.set_shuffle(bool(params.get("on")), client_ts)
    elif command == "radio_set_repeat":
        await manager.set_repeat(params.get("mode", "off"), client_ts)
    elif command == "radio_add_to_queue":
        track = db.query(RadioTrack).filter(RadioTrack.id == params.get("track_id")).first()
        if not track:
            raise _not_found(command, manager.channel, f"Morceau {params.get('track_id')}")
        if not track.available:
            await _reject_unavailable(command, manager.channel, track.title, db)
        await manager.add_to_queue(radio_track_dict(track), client_ts)
    elif command == "radio_play_next":
        track = db.query(RadioTrack).filter(RadioTrack.id == params.get("track_id")).first()
        if not track:
            raise _not_found(command, manager.channel, f"Morceau {params.get('track_id')}")
        if not track.available:
            await _reject_unavailable(command, manager.channel, track.title, db)
        await manager.play_next(radio_track_dict(track), client_ts)
    elif command == "radio_move_in_queue":
        await manager.move_in_order(
            int(params.get("from_index", -1)), int(params.get("to_index", -1)), client_ts,
        )
    elif command == "radio_remove_from_queue":
        await manager.remove_from_order(int(params.get("index", -1)), client_ts)
    elif command == "radio_track_ended":
        raw_track_id = params.get("track_id")
        track_id = raw_track_id if isinstance(raw_track_id, int) and not isinstance(raw_track_id, bool) else None
        await _handle_radio_track_ended(manager, db, client_ts, track_id)
    elif command == "radio_play_announcement":
        announcement = radio_commands.resolve_announcement(db, params.get("announcement_id"))
        if not announcement:
            raise _not_found(command, manager.channel, "Rappel")
        await radio_commands.play_announcement_now(db, [manager], announcement, client_ts)
    elif command == "announcement_ended":
        await manager.announcement_ended(client_ts)
    elif command == "report_position":
        if is_kiosk and websocket is not None and not ws_manager.is_primary_kiosk(websocket):
            return
        await manager.report_position(float(params.get("position_seconds", 0)))
    else:
        logger.warning(f"Commande radio WebSocket inconnue reçue : {command}")
        raise CommandRejected("unknown_command", manager.channel, f"Commande radio inconnue : {command}.", 400)


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
