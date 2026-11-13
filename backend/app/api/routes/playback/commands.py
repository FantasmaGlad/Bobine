"""Exécution d'une commande de lecture vidéo ou audio sur le moteur de son canal."""

import logging

from fastapi import WebSocket
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.api.contract import DEFAULT_CHANNEL
from app.models import Background, Playlist, Video
from app.playback.manager import get_playback_manager
from app.radio_manager import is_radio_channel, normalize_radio_channel
from app.utils import video_sound
from app.utils.importer.formats import is_image_background
from app.utils.ws_manager import manager as ws_manager

from . import audio_commands, cinema_commands
from .context import Command
from .core import CommandRejected, _reject_unavailable, _resolve_channel
from .media_items import _build_playlist_video_items, _thumbnail_filename
from .radio_commands import _handle_radio_command

logger = logging.getLogger(__name__)


async def execute_command(
    message: dict,
    db: Session,
    websocket: WebSocket | None = None,
    is_kiosk: bool = False,
    default_channel: str = DEFAULT_CHANNEL,
) -> None:
    """Point d'entrée unique d'une commande de lecture, commun au WebSocket et à la façade REST."""
    try:
        await _handle_command(message, db, websocket, is_kiosk=is_kiosk, default_channel=default_channel)
    except (TypeError, ValueError) as exc:
        raw_channel = (message.get("params") or {}).get("channel") or default_channel
        raise CommandRejected("invalid_params", str(raw_channel), f"Paramètres invalides : {exc}", 422) from exc


async def _load(cmd: Command) -> None:
    await cmd.ensure_not_locked()
    video_id = cmd.params.get("video_id")
    video = await cmd.fetch(Video, video_id)
    if not video:
        raise cmd.not_found(f"Vidéo {video_id}")
    if not video.available:
        await _reject_unavailable(cmd.name, cmd.channel, video.title, cmd.db)
    await cmd.manager.load(
        video.id, video.title, video.duration_seconds, video.program, cmd.client_ts,
        release=video.release, thumbnail_url=_thumbnail_filename(video.thumbnail_path),
        description=video.description, audio_channels=video.audio_channels,
        audio_codec=video.audio_codec, fps=video.fps, bitrate_kbps=video.bitrate_kbps,
        width=video.width, height=video.height,
    )
    await cmd.log("video_started", video.title)


async def _load_background(cmd: Command) -> None:
    background_id = cmd.params.get("background_id")
    background = await cmd.fetch(Background, background_id)
    if not background:
        raise cmd.not_found(f"Fond animé {background_id}")
    await cmd.manager.load_background(background.id, background.title, is_image_background(background.file_path), cmd.client_ts)
    await cmd.log("background_started", background.title)


async def _load_playlist(cmd: Command) -> None:
    await cmd.ensure_not_locked()
    playlist_id = cmd.params.get("playlist_id")
    playlist = await cmd.fetch(Playlist, playlist_id)
    if not playlist:
        raise cmd.not_found(f"Playlist {playlist_id}")
    items = await run_in_threadpool(_build_playlist_video_items, playlist)
    if not items and await run_in_threadpool(lambda: bool(playlist.items)):
        await _reject_unavailable(cmd.name, cmd.channel, playlist.name, cmd.db)
    await cmd.manager.load_playlist(playlist.id, playlist.name, items, cmd.client_ts)
    await cmd.log("playlist_started", playlist.name)


async def _stop(cmd: Command) -> None:
    current = cmd.manager.snapshot()
    playing = [current[key] for key in ("current_video", "current_background", "current_audio_course") if current[key]]
    if playing:
        await cmd.log("playback_stopped", next((item.get("title") for item in playing if item.get("title")), None))
    await cmd.manager.stop(cmd.client_ts)


def _video_id(raw) -> int | None:
    if isinstance(raw, (int, float, str)) and str(raw).lstrip("-").isdigit():
        return int(raw)
    return None


async def _video_ended(cmd: Command) -> None:
    current = cmd.manager.state.get("current_video") or {}
    ended_id = _video_id(cmd.params.get("video_id"))
    was_current = cmd.manager.state["state"] == "playing" and ended_id in (None, current.get("id"))
    await cmd.manager.video_ended(cmd.client_ts, video_id=ended_id)
    if current.get("title") and was_current:
        await cmd.log("video_ended", current.get("title"))


async def _report_position(cmd: Command) -> None:
    if not cmd.secondary_kiosk():
        await cmd.manager.report_position(float(cmd.params.get("position_seconds", 0)))


_VIDEO = {
    "load": _load,
    "load_background": _load_background,
    "load_playlist": _load_playlist,
    "stop": _stop,
    "video_ended": _video_ended,
    "report_position": _report_position,
    "play": lambda cmd: cmd.manager.play(cmd.client_ts),
    "pause": lambda cmd: cmd.manager.pause(cmd.client_ts),
    "seek": lambda cmd: cmd.manager.seek(float(cmd.params.get("position_seconds", 0)), cmd.client_ts),
    "volume": lambda cmd: cmd.manager.set_volume(cmd.params.get("volume", 100), cmd.client_ts),
    "speed": lambda cmd: cmd.manager.set_speed(cmd.params.get("speed", 1.0), cmd.client_ts),
    "set_sound": lambda cmd: video_sound.apply_video_sound(cmd.db, cmd.manager, cmd.params.get("sound"), cmd.client_ts),
    "set_subtitle": lambda cmd: cmd.manager.set_subtitle(cmd.params.get("subtitle"), cmd.client_ts),
    "next_video": lambda cmd: cmd.manager.next_video(cmd.client_ts),
    "previous_video": lambda cmd: cmd.manager.previous_video(cmd.client_ts),
    "skip_waiting": lambda cmd: cmd.manager.skip_waiting(cmd.client_ts),
}
_HANDLERS = {**_VIDEO, **audio_commands.HANDLERS, **cinema_commands.HANDLERS}


async def _handle_command(
    message: dict,
    db: Session,
    websocket: WebSocket | None = None,
    is_kiosk: bool = False,
    default_channel: str = DEFAULT_CHANNEL,
) -> None:
    command = message.get("command")
    params = message.get("params") or {}
    client_ts = params.get("client_ts")
    if command == "pong":
        if websocket is not None:
            ws_manager.note_pong(websocket)
        return
    raw_channel = params.get("channel") or default_channel
    if is_radio_channel(raw_channel):
        await _handle_radio_command(command, params, client_ts, db, websocket, is_kiosk,
                                    radio_channel=normalize_radio_channel(raw_channel))
        return
    channel = _resolve_channel(raw_channel)
    handler = _HANDLERS.get(command)
    if handler is None:
        logger.warning(f"Commande WebSocket inconnue reçue : {command}")
        raise CommandRejected("unknown_command", channel, f"Commande inconnue : {command}.", 400)
    await handler(Command(command, params, client_ts, db, websocket, is_kiosk, channel, get_playback_manager(channel)))
