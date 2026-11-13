"""Commandes du mode cinéma : rapports du lecteur et ordres relayés aux écrans."""

from datetime import datetime

from fastapi.concurrency import run_in_threadpool

from app.utils.playback_session_tracker import (
    close_playback_session,
    start_playback_session,
    update_playback_session_progress,
)
from app.utils.ws_manager import manager as ws_manager

from .cinema import _apply_cinema_command_to_clock, _cinema_clock_for, _cinema_launched_video
from .context import Command
from .core import CommandRejected, _cinema_sessions

_ACTIONS = ("play", "pause", "seek", "stop", "launch")


async def _close_session(cmd: Command, *position: float) -> None:
    session_id = _cinema_sessions.pop(cmd.channel)
    await run_in_threadpool(close_playback_session, cmd.db, session_id, *position)


async def _open_session(cmd: Command, video_id: int, kind: str, duration: float) -> None:
    session_id = await run_in_threadpool(start_playback_session, cmd.db, video_id, cmd.channel, kind, duration)
    if session_id:
        _cinema_sessions[cmd.channel] = session_id


async def cinema_report(cmd: Command) -> None:
    position, duration = cmd.number("position_seconds"), cmd.number("duration_seconds")
    video_id = cmd.params.get("video_id")
    playing = bool(cmd.params.get("playing"))
    if playing and video_id:
        if cmd.channel not in _cinema_sessions:
            await _open_session(cmd, int(video_id), "cinema", duration)
        else:
            await run_in_threadpool(update_playback_session_progress, cmd.db, _cinema_sessions[cmd.channel], position)
    elif not cmd.params.get("title") and cmd.channel in _cinema_sessions:
        await _close_session(cmd, position)
    await ws_manager.broadcast({
        "event": "cinema_state",
        "channel": cmd.channel,
        "data": {
            "title": cmd.params.get("title"),
            "program": cmd.params.get("program"),
            "position_seconds": position,
            "duration_seconds": duration,
            "playing": playing,
            "video_id": video_id,
            "reported_at": datetime.now().timestamp(),
        },
    })


async def cinema_command(cmd: Command) -> None:
    action = cmd.params.get("action")
    if action not in _ACTIONS:
        raise CommandRejected("invalid_params", cmd.channel, f"Action cinéma inconnue : {action} (play, pause, seek, stop, launch).", 422)
    if action == "launch" and cmd.params.get("video_id"):
        if cmd.channel in _cinema_sessions:
            await _close_session(cmd)
        kind = "grid" if cmd.params.get("source") == "grid" or not cmd.is_kiosk else "cinema"
        await _open_session(cmd, int(cmd.params.get("video_id")), kind, cmd.number("duration_seconds"))
    elif action == "stop" and cmd.channel in _cinema_sessions:
        await _close_session(cmd, cmd.number("position_seconds"))
    _apply_cinema_command_to_clock(cmd.channel, action, cmd.params)
    payload = {
        "event": "cinema_command",
        "channel": cmd.channel,
        "action": action,
        "position_seconds": cmd.number("position_seconds"),
        "video_id": cmd.params.get("video_id"),
    }
    launched = _cinema_launched_video.get(cmd.channel)
    if launched is not None and action != "stop":
        payload["clock"] = _cinema_clock_for(cmd.channel).to_dict()
        payload["clock_video_id"] = launched
    for key in ("title", "duration_seconds"):
        if key in cmd.params:
            payload[key] = cmd.params[key]
    await ws_manager.broadcast(payload)


HANDLERS = {"cinema_report": cinema_report, "cinema_command": cinema_command}
