"""Pilote Linux : PipeWire (audio), BlueZ par D-Bus (Bluetooth), NetworkManager (Wi-Fi)."""

from __future__ import annotations

import asyncio
import logging
import shutil
import time
from typing import Any

from ..base import CAPABILITY_KEYS, DeviceDriver
from .audio import AudioMixin
from .audio_routing import AudioRoutingMixin
from .bluetooth import BluetoothMixin
from .command import Runner, run_command
from .pairing import PairingMixin
from .wifi import WifiMixin

logger = logging.getLogger(__name__)

_PROBE_TTL = 30.0
_AUDIO_BASE = ("audio_list", "audio_set_default", "audio_set_volume")
_AUDIO_TOOLS = (("audio_balance", "pw-cli"), ("audio_test_tone", "pw-play"), ("audio_profile", "wpctl"), ("audio_route_stream", "pw-metadata"))
_BLUETOOTH = ("bluetooth_status", "bluetooth_power", "bluetooth_scan", "bluetooth_pair", "bluetooth_connect", "bluetooth_forget")
_WIFI = ("wifi_status", "wifi_power", "wifi_scan", "wifi_connect", "wifi_forget")


def _support(reason: str | None) -> dict[str, Any]:
    return {"supported": True} if reason is None else {"supported": False, "reason": reason}


class LinuxDriver(AudioMixin, AudioRoutingMixin, BluetoothMixin, PairingMixin, WifiMixin, DeviceDriver):
    name = "linux"

    def __init__(self, runner: Runner = run_command) -> None:
        super().__init__()
        self._run = runner
        self._bus: Any = None
        self._bus_lock = asyncio.Lock()
        self._agent: Any = None
        self._pending: dict[str, Any] | None = None
        self._pending_future: asyncio.Future[bool] | None = None
        self._pairing: dict[str, Any] | None = None
        self._tone_lock = asyncio.Lock()
        self._moved_streams: dict[int, str] = {}
        self._route_lock = asyncio.Lock()
        self._probe_cache: tuple[float, dict[str, dict[str, Any]]] | None = None
        self._wifi_device_cache: tuple[float, dict[str, str] | None] = (0.0, None)

    async def stop(self) -> None:
        bus, self._bus = self._bus, None
        if bus is not None:
            try:
                bus.disconnect()
            except Exception as exc:
                logger.debug("stop : %s", exc)

    async def capabilities(self) -> dict[str, dict[str, Any]]:
        now = time.monotonic()
        if self._probe_cache and now - self._probe_cache[0] < _PROBE_TTL:
            return self._probe_cache[1]
        caps: dict[str, dict[str, Any]] = {k: {"supported": False, "reason": ""} for k in CAPABILITY_KEYS}
        audio_reason = await self._probe_audio()
        caps.update({key: _support(audio_reason) for key in (*_AUDIO_BASE, "audio_details")})
        for key, tool in _AUDIO_TOOLS:
            missing = None if shutil.which(tool) else f"L'outil {tool} n'est pas installé."
            caps[key] = _support(audio_reason or missing)
        bt_reason = await self._probe_bluetooth()
        caps.update({key: _support(bt_reason) for key in _BLUETOOTH})
        wifi_reason = await self._probe_wifi()
        caps.update({key: _support(wifi_reason) for key in _WIFI})
        caps["system_settings"] = _support("Non applicable sur ce système : utilisez cet écran.")
        self._probe_cache = (now, caps)
        return caps

    def _invalidate_probe(self) -> None:
        self._probe_cache = None
