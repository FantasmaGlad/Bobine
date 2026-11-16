"""PipeWire : sorties, détails, balance, son de test, profils, volume."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import tempfile
from typing import Any

from app.api.contract import AUDIO_TEST_CHANNELS

from ..base import DeviceError, unsupported
from .parse.audio import parse_pw_dump, parse_wpctl_volume
from .parse.audio_details import channel_volumes_for_balance, parse_audio_details, tone_wav_bytes


class AudioMixin:
    async def _probe_audio(self) -> str | None:
        if not (shutil.which("pw-dump") and shutil.which("wpctl")):
            return "PipeWire (pw-dump, wpctl) n'est pas installé sur cette machine."
        try:
            code, _, _ = await self._run("wpctl", "status", timeout=4)
        except DeviceError as exc:
            return exc.message
        return None if code == 0 else "PipeWire ne répond pas pour le compte qui exécute Bobine."

    async def _pw_dump_json(self) -> Any:
        code, out, err = await self._run("pw-dump", timeout=8)
        _check(code, err, "PipeWire ne répond pas.", "audio_unavailable")
        try:
            return json.loads(out)
        except ValueError as exc:
            raise DeviceError("audio_unavailable", "Réponse PipeWire illisible.", 502) from exc

    async def _pw_dump_raw(self) -> list[dict[str, Any]]:
        data = await self._pw_dump_json()
        return data if isinstance(data, list) else []

    async def _audio_sinks(self) -> dict[str, Any]:
        data = await self._pw_dump_json()
        try:
            return parse_pw_dump(data)
        except (ValueError, KeyError, TypeError) as exc:
            raise DeviceError("audio_unavailable", "Réponse PipeWire illisible.", 502) from exc

    async def _details(self, device_id: str) -> dict[str, Any]:
        details = parse_audio_details(await self._pw_dump_raw(), device_id)
        if details is None:
            raise DeviceError("not_found", "Cette sortie audio n'est plus disponible.", 404)
        return details

    async def audio_list(self) -> dict[str, Any]:
        reason = await self._probe_audio()
        if reason:
            return unsupported(reason)
        data = await self._audio_sinks()

        async def with_volume(sink: dict[str, Any]) -> dict[str, Any]:
            try:
                _, out, _ = await self._run("wpctl", "get-volume", str(sink["pw_id"]), timeout=4)
                volume, muted = parse_wpctl_volume(out)
            except DeviceError:
                volume, muted = None, None
            return {**{k: v for k, v in sink.items() if k != "pw_id"}, "volume": volume, "muted": muted}

        devices = await asyncio.gather(*(with_volume(s) for s in data["sinks"]))
        devices.sort(key=lambda d: (not d["is_default"], d["name"].lower()))
        return {"supported": True, "devices": devices, "default_id": data["default_id"]}

    async def audio_details(self, device_id: str) -> dict[str, Any]:
        reason = await self._probe_audio()
        if reason:
            return unsupported(reason)
        details = await self._details(device_id)
        public = {k: v for k, v in details.items() if k not in ("device_pw_id", "node_pw_id", "channel_volumes")}
        return {"supported": True, **public}

    async def audio_set_balance(self, device_id: str, balance: float) -> None:
        if not shutil.which("pw-cli"):
            raise DeviceError("tool_missing", "L'outil pw-cli est introuvable : la balance n'est pas réglable.", 501)
        details = await self._details(device_id)
        volumes = details["channel_volumes"]
        if len(volumes) != 2:
            raise DeviceError("unsupported", "La balance n'existe que pour une sortie stéréo.", 501)
        left, right = channel_volumes_for_balance(volumes, balance)
        code, _, err = await self._run("pw-cli", "set-param", str(details["node_pw_id"]), "Props", f"{{ channelVolumes: [{left:.6f}, {right:.6f}] }}", timeout=5)
        _check(code, err, "Réglage de la balance refusé.")
        self._emit("audio")

    async def audio_test_tone(self, device_id: str, channel: str) -> None:
        if channel not in AUDIO_TEST_CHANNELS:
            raise DeviceError("bad_channel", "Canal de test inconnu.", 400)
        if not shutil.which("pw-play"):
            raise DeviceError("tool_missing", "L'outil pw-play est introuvable : le son de test n'est pas disponible.", 501)
        if self._tone_lock.locked():
            raise DeviceError("busy", "Un son de test est déjà en cours.", 409)
        async with self._tone_lock:
            await self._details(device_id)
            with tempfile.TemporaryDirectory(prefix="bobine_tone_") as tmp:
                path = os.path.join(tmp, "tone.wav")
                with open(path, "wb") as handle:
                    handle.write(tone_wav_bytes(channel))
                code, _, err = await self._run("pw-play", "--target", device_id, "--volume", "0.5", path, timeout=6)
            _check(code, err, "Lecture du son de test impossible.")

    async def audio_set_profile(self, device_id: str, profile_index: int) -> None:
        details = await self._details(device_id)
        if details.get("device_pw_id") is None or not any(p["index"] == profile_index and p["available"] for p in details["profiles"]):
            raise DeviceError("bad_profile", "Profil audio indisponible pour cette sortie.", 400)
        code, _, err = await self._run("wpctl", "set-profile", str(details["device_pw_id"]), str(profile_index), timeout=6)
        _check(code, err, "Changement de profil refusé.")
        self._emit("audio")

    async def _pw_id(self, device_id: str) -> int:
        data = await self._audio_sinks()
        for sink in data["sinks"]:
            if sink["id"] == device_id:
                return int(sink["pw_id"])
        raise DeviceError("not_found", "Cette sortie audio n'est plus disponible.", 404)

    async def audio_set_default(self, device_id: str) -> None:
        pw_id = await self._pw_id(device_id)
        code, _, err = await self._run("wpctl", "set-default", str(pw_id), timeout=5)
        _check(code, err, "Changement de sortie refusé.")
        self._emit("audio")

    async def audio_set_volume(self, device_id: str, volume: float | None, muted: bool | None) -> None:
        pw_id = await self._pw_id(device_id)
        if volume is not None:
            code, _, err = await self._run("wpctl", "set-volume", str(pw_id), f"{max(0.0, min(1.5, volume)):.2f}", timeout=5)
            _check(code, err, "Réglage du volume refusé.")
        if muted is not None:
            code, _, err = await self._run("wpctl", "set-mute", str(pw_id), "1" if muted else "0", timeout=5)
            _check(code, err, "Réglage du son coupé refusé.")
        self._emit("audio")


def _check(code: int, err: str, fallback: str, error: str = "audio_failed") -> None:
    if code != 0:
        raise DeviceError(error, (err.strip() or fallback)[:200], 502)
