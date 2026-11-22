"""Registre des entrées (clavier, télécommande, manette) et des actions de lecture qu'elles déclenchent."""

from __future__ import annotations

REMOTE_ACTIONS = (
    "left", "right", "up", "down", "enter", "back", "play_pause", "next", "prev",
    "chapter_next", "chapter_prev", "volume_up", "volume_down", "mute",
)

GAMEPAD_DIRECTIONS = {12: "up", 13: "down", 14: "left", 15: "right"}
ANALOG_TRIGGERS = (6, 7)

def _keys(names: tuple[str, ...], actions: tuple[str, ...]) -> list[tuple[str, tuple[str, ...]]]:
    return [(f"key:{name}", actions) for name in names]


def _codes(values: tuple[int, ...], actions: tuple[str, ...]) -> list[tuple[str, tuple[str, ...]]]:
    return [(f"code:{value}", actions) for value in values]


def _pad(button: int, actions: tuple[str, ...]) -> list[tuple[str, tuple[str, ...]]]:
    return [(f"pad:{button}", actions)]


DEFAULT_BINDINGS: dict[str, tuple[str, ...]] = dict([
    *_keys(("ArrowLeft",), ("left",)),
    *_keys(("ArrowRight",), ("right",)),
    *_keys(("ArrowUp",), ("up",)),
    *_keys(("ArrowDown",), ("down",)),
    *_keys(("Enter", "Select", "Ok"), ("enter",)),
    *_keys(("Escape", "Backspace", "BrowserBack", "GoBack", "Back", "MediaStop"), ("back",)),
    *_keys((" ", "Spacebar"), ("play_pause", "enter")),
    *_keys(("MediaPlayPause", "MediaPlay", "MediaPause", "Play", "Pause"), ("play_pause",)),
    *_keys(("MediaTrackNext", "FastForward", "MediaFastForward"), ("next",)),
    *_keys(("MediaTrackPrevious", "Rewind", "MediaRewind"), ("prev",)),
    *_keys(("ChannelUp",), ("chapter_next", "next")),
    *_keys(("ChannelDown",), ("chapter_prev", "prev")),
    *_keys(("PageDown",), ("next", "down")),
    *_keys(("PageUp",), ("prev", "up")),
    *_keys(("AudioVolumeUp", "VolumeUp"), ("volume_up",)),
    *_keys(("AudioVolumeDown", "VolumeDown"), ("volume_down",)),
    *_keys(("AudioVolumeMute", "VolumeMute"), ("mute",)),
    *_codes((4,), ("back",)),
    *_codes((19,), ("up",)),
    *_codes((20,), ("down",)),
    *_codes((21,), ("left",)),
    *_codes((22,), ("right",)),
    *_codes((23, 66), ("enter",)),
    *_codes((24,), ("volume_up",)),
    *_codes((25,), ("volume_down",)),
    *_codes((164,), ("mute",)),
    *_codes((85, 126, 127), ("play_pause",)),
    *_codes((87,), ("next",)),
    *_codes((88,), ("prev",)),
    *_codes((166,), ("chapter_next", "next")),
    *_codes((167,), ("chapter_prev", "prev")),
    *_pad(12, ("up",)),
    *_pad(13, ("down",)),
    *_pad(14, ("left",)),
    *_pad(15, ("right",)),
    *_pad(0, ("enter", "play_pause")),
    *_pad(1, ("back",)),
    *_pad(2, ("play_pause",)),
    *_pad(3, ("play_pause",)),
    *_pad(4, ("prev",)),
    *_pad(5, ("next",)),
    *_pad(6, ("volume_down",)),
    *_pad(7, ("volume_up",)),
    *_pad(8, ("back",)),
    *_pad(9, ("play_pause",)),
])
