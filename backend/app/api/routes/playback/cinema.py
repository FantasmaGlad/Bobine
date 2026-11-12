"""Horloges des cours lancés sur les écrans cinéma d'un canal."""

from app.utils.playback_clock import PlaybackClock

_cinema_clocks: dict[str, PlaybackClock] = {}
_cinema_launched_video: dict[str, int] = {}


def _cinema_clock_for(channel: str) -> PlaybackClock:
    clock = _cinema_clocks.get(channel)
    if clock is None:
        clock = _cinema_clocks[channel] = PlaybackClock()
    return clock


def _apply_cinema_command_to_clock(channel: str, action: str, params: dict) -> None:
    clock = _cinema_clock_for(channel)
    if action == "launch" and params.get("video_id"):
        _cinema_launched_video[channel] = int(params["video_id"])
        clock.reset()
        clock.start(max(0.0, float(params.get("position_seconds") or 0)))
        return
    if channel not in _cinema_launched_video:
        return
    if action == "stop":
        _cinema_launched_video.pop(channel, None)
        clock.reset()
    elif action == "pause":
        clock.pause()
    elif action == "play":
        if not clock.running:
            clock.start()
    elif action == "seek":
        clock.seek(max(0.0, float(params.get("position_seconds") or 0)))
