#!/usr/bin/env python3
"""Test réel du routage audio Linux (phase 2 des périphériques) sur de VRAIS flux PipeWire, sans toucher au matériel.

Ce que fait le script :
  1. crée deux puits virtuels « null » (`bobine-test-a`, `bobine-test-b`) dans la session PipeWire courante ;
  2. lance un flux de lecture de SILENCE (`pw-play`), présenté comme un navigateur, vers `bobine-test-a` ;
  3. demande à `LinuxDriver.audio_route_stream` de l'amener vers `bobine-test-b` et vérifie par `pw-dump` qu'il y est ;
  4. le rend (`None`) et vérifie qu'il a quitté `bobine-test-b` ;
  5. supprime tout (les puits virtuels disparaissent avec leur processus).

Aucune sortie réelle n'est modifiée (ni sortie par défaut, ni volume, ni profil) ; le flux ne joue que du silence. Si un
vrai flux de navigateur est en lecture sur la machine, le test est inconcluant (le routage refuse de deviner) et s'arrête.

Usage : backend/.venv/bin/python scripts/devices-real-test.py
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.devices.linux import LinuxDriver, run_command  # noqa: E402
from app.devices.linux_parse import parse_output_streams  # noqa: E402

SINKS = ("bobine-test-a", "bobine-test-b")
results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"[{'OK ' if ok else 'ÉCHEC'}] {name}{' — ' + detail if detail else ''}")


def dump() -> list[dict]:
    return json.loads(subprocess.run(["pw-dump"], capture_output=True, text=True, timeout=10).stdout)


def stream_sink(stream_id: int) -> str | None:
    streams = {s["id"]: s for s in parse_output_streams(dump())}
    return streams.get(stream_id, {}).get("sink")


def silence_file(directory: str, seconds: int = 60) -> str:
    path = os.path.join(directory, "silence.wav")
    with wave.open(path, "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(48000)
        wav.writeframes(struct.pack("<hh", 0, 0) * 48000 * seconds)
    return path


def main() -> int:
    for tool in ("pw-dump", "pw-cli", "pw-play", "pw-metadata", "wpctl"):
        if not shutil.which(tool):
            print(f"Outil absent ({tool}) : test sans objet sur cette machine.")
            return 0
    if subprocess.run(["wpctl", "status"], capture_output=True, timeout=5).returncode != 0:
        print("PipeWire ne répond pas : test sans objet.")
        return 0
    if any(s["browser"] and s["state"] == "running" for s in parse_output_streams(dump())):
        print("Un flux de navigateur est en lecture sur cette machine : test inconcluant (le routage refuse de deviner). Arrêtez-le et relancez.")
        return 0

    pw_cli = subprocess.Popen(["pw-cli"], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True)
    player: subprocess.Popen | None = None
    try:
        for name in SINKS:
            pw_cli.stdin.write(
                "create-node adapter { factory.name=support.null-audio-sink node.name=%s node.description=%s "
                "media.class=Audio/Sink object.linger=false audio.position=[FL FR] }\n" % (name, name)
            )
        pw_cli.stdin.flush()
        time.sleep(1.0)
        names = {obj["info"]["props"].get("node.name") for obj in dump() if (obj.get("info") or {}).get("props")}
        check("puits virtuels créés", all(n in names for n in SINKS))

        with tempfile.TemporaryDirectory(prefix="bobine_devtest_") as tmp:
            player = subprocess.Popen(
                ["pw-play", "--target", SINKS[0], "-P", "{ application.name = Chromium, application.process.binary = chromium }", silence_file(tmp)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            stream = None
            for _ in range(30):
                found = [s for s in parse_output_streams(dump()) if s["browser"] and s["state"] == "running"]
                if found:
                    stream = found[0]
                    break
                time.sleep(0.2)
            check("flux de lecture présenté comme un navigateur détecté", stream is not None)
            if stream is None:
                return 1
            check("il joue vers le premier puits", stream["sink"] == SINKS[0], str(stream["sink"]))

            driver = LinuxDriver(runner=run_command)
            moved = asyncio.run(driver.audio_route_stream(SINKS[1]))
            check("déplacement vers le second puits", moved.get("status") == "moved", json.dumps(moved))
            check("vérifié par pw-dump", stream_sink(stream["id"]) == SINKS[1], str(stream_sink(stream["id"])))
            again = asyncio.run(driver.audio_route_stream(SINKS[1]))
            check("second appel : rien à faire", again.get("status") == "unchanged", json.dumps(again))

            released = asyncio.run(driver.audio_route_stream(None))
            time.sleep(0.8)
            check("flux rendu", released.get("status") == "released" and stream_sink(stream["id"]) != SINKS[1], f"{released} -> {stream_sink(stream['id'])}")

            gone = asyncio.run(_expect_error(driver))
            check("sortie inconnue : erreur structurée 404", gone == (404, "not_found"), str(gone))
    finally:
        if player is not None:
            player.terminate()
            player.wait(timeout=5)
        pw_cli.terminate()
        pw_cli.wait(timeout=5)
        time.sleep(0.5)
    left = [s for s in SINKS if any(((o.get("info") or {}).get("props") or {}).get("node.name") == s for o in dump())]
    check("puits virtuels supprimés", not left, ", ".join(left))
    failed = [name for name, ok, _ in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} vérifications réussies")
    return 1 if failed else 0


async def _expect_error(driver: LinuxDriver) -> tuple[int, str] | None:
    from app.devices.base import DeviceError

    try:
        await driver.audio_route_stream("bobine-test-inexistante")
    except DeviceError as exc:
        return exc.status, exc.code
    return None


if __name__ == "__main__":
    sys.exit(main())
