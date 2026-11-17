"""Délais et modes du moteur radio."""

from __future__ import annotations

from typing import Awaitable, Callable

BroadcastFn = Callable[[dict], Awaitable[None]]


REPEAT_MODES = ("off", "playlist", "track")


HEARTBEAT_SECONDS = 1.0


TRACK_END_GRACE_SECONDS = 2.0


PLAY_LEAD_MS = 150.0


METER_LEASE_SECONDS = 12.0
