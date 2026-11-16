"""Routage du flux de la radio vers une sortie PipeWire, vérifié puis annulable."""

from __future__ import annotations

import asyncio
import shutil
from typing import Any

from ..base import DeviceError
from .parse.audio import choose_browser_stream, parse_output_streams


class AudioRoutingMixin:
    async def _output_streams(self) -> list[dict[str, Any]]:
        return parse_output_streams(await self._pw_dump_raw())

    async def audio_route_stream(self, sink_id: str | None) -> dict[str, Any]:
        """Déplace le flux du navigateur qui joue la radio vers `sink_id` (`pw-metadata … target.object`), puis VÉRIFIE par `pw-dump` que le flux est bien relié à cette sortie ; sinon retour arrière."""
        if not shutil.which("pw-metadata"):
            raise DeviceError("tool_missing", "L'outil pw-metadata est introuvable : le routage système n'est pas disponible.", 501)
        async with self._route_lock:
            streams = await self._output_streams()
            if sink_id is None:
                return await self._release_streams(streams)
            await self._pw_id(sink_id)
            verdict, stream = choose_browser_stream(streams)
            if stream is None:
                return {"status": "ambiguous" if verdict == "ambiguous" else "no_stream"}
            if stream["sink"] == sink_id:
                return {"status": "unchanged", "app": stream["app"]}
            code, _, err = await self._run("pw-metadata", "-n", "default", str(stream["id"]), "target.object", sink_id, "Spa:String", timeout=5)
            if code != 0:
                return {"status": "failed", "app": stream["app"], "detail": (err.strip() or "pw-metadata a échoué.")[:200]}
            for _ in range(8):
                await asyncio.sleep(0.25)
                moved = next((s for s in await self._output_streams() if s["id"] == stream["id"]), None)
                if moved is not None and moved["sink"] == sink_id:
                    self._moved_streams[stream["id"]] = sink_id
                    self._emit("audio")
                    return {"status": "moved", "app": stream["app"]}
            await self._run("pw-metadata", "-n", "default", "-d", str(stream["id"]), "target.object", timeout=5)
            return {"status": "failed", "app": stream["app"], "detail": "Le flux n'a pas rejoint la sortie demandée."}

    async def _release_streams(self, streams: list[dict[str, Any]]) -> dict[str, Any]:
        alive = {s["id"] for s in streams}
        released = 0
        for stream_id in list(self._moved_streams):
            if stream_id in alive:
                code, _, _ = await self._run("pw-metadata", "-n", "default", "-d", str(stream_id), "target.object", timeout=5)
                released += 1 if code == 0 else 0
            self._moved_streams.pop(stream_id, None)
        return {"status": "released" if released else "unchanged"}
