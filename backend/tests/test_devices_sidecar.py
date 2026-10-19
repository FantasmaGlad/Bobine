"""Pilote sidecar (Windows/macOS) : protocole JSON-RPC, garde-fou « expérimental », reprise après
panne, délais d'expiration. Un faux sidecar (script Python) joue le rôle du binaire Rust ; le vrai
binaire est aussi exercé quand il a été compilé (`devices/target/release`)."""

import asyncio
import os
import sys
import textwrap
from pathlib import Path

import pytest

from app.devices.base import DeviceError
from app.devices.sidecar import EXPERIMENTAL_ENV, SidecarDriver, find_binary

FAKE = textwrap.dedent(
    '''
    import json, os, sys, time
    mode = os.environ.get("FAKE_MODE", "ok")
    for line in sys.stdin:
        req = json.loads(line)
        method, rid = req["method"], req["id"]
        if method == "hello":
            version = 99 if mode == "badversion" else 1
            out = {"protocol_version": version, "platform": "fake", "capabilities": {"audio_list": {"supported": True}}}
        elif method == "audio.list":
            if mode == "crash":
                sys.exit(3)
            if mode == "hang":
                time.sleep(30)
            out = {"supported": True, "devices": [{"id": "a", "name": "A"}], "default_id": "a"}
        elif method == "wifi.connect":
            print(json.dumps({"jsonrpc": "2.0", "id": rid, "error": {"code": -32000, "message": "refus", "data": {"code": "wifi_auth_failed"}}}), flush=True)
            continue
        elif method == "wifi.forget":
            print(json.dumps({"jsonrpc": "2.0", "id": rid + 1000, "result": None}), flush=True)
            continue
        elif method == "wifi.current_connection":
            out = "Maison"
        elif method == "bluetooth.pair":
            print(json.dumps({"jsonrpc": "2.0", "id": rid, "error": {"code": -32602, "message": "adresse invalide"}}), flush=True)
            continue
        else:
            out = None
        print(json.dumps({"jsonrpc": "2.0", "id": rid, "result": out}), flush=True)
    '''
)


@pytest.fixture()
def fake_script(tmp_path):
    path = tmp_path / "fake_sidecar.py"
    path.write_text(FAKE)
    return [sys.executable, str(path)]


def run(coro):
    return asyncio.run(coro)


def test_blocked_until_experimental_flag(fake_script, monkeypatch):
    monkeypatch.delenv(EXPERIMENTAL_ENV, raising=False)
    driver = SidecarDriver("windows", command=fake_script)

    async def scenario():
        caps = await driver.capabilities()
        assert all(not c["supported"] for c in caps.values())
        assert "validation" in caps["audio_list"]["reason"] and EXPERIMENTAL_ENV in caps["audio_list"]["reason"]
        assert (await driver.audio_list())["supported"] is False
        with pytest.raises(DeviceError) as exc:
            await driver.wifi_connect("X", None)
        assert exc.value.code == "unsupported"
        assert driver._proc is None  # rien n'a été lancé

    run(scenario())


def test_missing_binary_is_reported(monkeypatch):
    monkeypatch.delenv("BOBINE_DEVICES_SIDECAR", raising=False)
    driver = SidecarDriver("macos", command=None, experimental=True)
    driver._command = None
    caps = run(driver.capabilities())
    assert "introuvable" in caps["audio_list"]["reason"]


def test_hello_capabilities_and_calls(fake_script, monkeypatch):
    monkeypatch.delenv("FAKE_MODE", raising=False)
    driver = SidecarDriver("macos", command=fake_script, experimental=True)
    events = []
    driver.set_change_callback(events.append)

    async def scenario():
        assert (await driver.capabilities())["audio_list"]["supported"] is True
        listing = await driver.audio_list()
        assert listing["default_id"] == "a"
        assert await driver.wifi_current_connection() == "Maison"
        await driver.wifi_set_power(True)
        assert "wifi" in events
        await driver.stop()

    run(scenario())


def test_rpc_errors_become_device_errors(fake_script):
    driver = SidecarDriver("macos", command=fake_script, experimental=True)

    async def scenario():
        with pytest.raises(DeviceError) as auth:
            await driver.wifi_connect("X", "pw")
        assert (auth.value.code, auth.value.status) == ("wifi_auth_failed", 400)
        with pytest.raises(DeviceError) as bad:
            await driver.bluetooth_pair("AA:BB:CC:DD:EE:FF")
        assert (bad.value.code, bad.value.status) == ("bad_params", 400)
        await driver.stop()

    run(scenario())


def test_protocol_version_mismatch_is_refused(fake_script, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "badversion")
    driver = SidecarDriver("windows", command=fake_script, experimental=True)

    async def scenario():
        with pytest.raises(DeviceError) as exc:
            await driver.audio_set_default("x")
        assert exc.value.code == "sidecar_version"
        caps = await driver.capabilities()
        assert not caps["audio_list"]["supported"]

    run(scenario())


def test_desynchronised_reply_kills_the_process(fake_script):
    driver = SidecarDriver("windows", command=fake_script, experimental=True)

    async def scenario():
        with pytest.raises(DeviceError) as exc:
            await driver.wifi_forget("X")  # le faux sidecar répond avec un mauvais identifiant
        assert exc.value.code == "sidecar_protocol"
        assert driver._proc is None
        assert await driver.wifi_current_connection() == "Maison"  # relancé au prochain appel
        await driver.stop()

    run(scenario())


def test_crash_then_automatic_restart(fake_script, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "crash")
    driver = SidecarDriver("windows", command=fake_script, experimental=True)

    async def scenario():
        with pytest.raises(DeviceError) as exc:
            await driver.audio_list()
        assert exc.value.code == "sidecar_down"
        monkeypatch.setenv("FAKE_MODE", "ok")
        assert (await driver.audio_list())["supported"] is True
        await driver.stop()

    run(scenario())


def test_hung_sidecar_times_out_and_is_killed(fake_script, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "hang")
    driver = SidecarDriver("windows", command=fake_script, experimental=True)

    async def scenario():
        with pytest.raises(DeviceError) as exc:
            await driver._rpc("audio.list", timeout=0.5)
        assert exc.value.code == "timeout" and exc.value.status == 504
        assert driver._proc is None

    run(scenario())


REAL = Path(__file__).resolve().parents[2] / "devices" / "target" / "release" / "bobine-devices"


@pytest.mark.skipif(not REAL.is_file() or os.name == "nt", reason="binaire bobine-devices non compilé")
def test_real_binary_speaks_the_protocol_and_refuses_unknown_methods():
    """Sur Linux le binaire déclare « plateforme non prise en charge » (Linux passe par D-Bus), mais le
    protocole (hello, liste blanche, validation) est celui de Windows/macOS."""
    driver = SidecarDriver("macos", command=[str(REAL)], experimental=True)

    async def scenario():
        caps = await driver.capabilities()
        assert not caps["wifi_connect"]["supported"]
        assert (await driver.audio_list())["supported"] is False
        with pytest.raises(DeviceError) as exc:
            await driver._rpc("system.exec", {"cmd": "id"})
        assert exc.value.code == "sidecar_error"  # méthode introuvable : jamais exécutée
        with pytest.raises(DeviceError) as bad:
            await driver.bluetooth_pair("pas-une-adresse")
        assert bad.value.code == "bad_params"
        await driver.stop()

    run(scenario())


def test_find_binary_respects_override(tmp_path, monkeypatch):
    binary = tmp_path / "bobine-devices"
    binary.write_text("x")
    monkeypatch.setenv("BOBINE_DEVICES_SIDECAR", str(binary))
    assert find_binary("windows") == [str(binary)]
