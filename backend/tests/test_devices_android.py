"""Pilote Android : pont Kotlin simulé (aucun appareil requis). Vérifie la correspondance des
erreurs, l'état « autorisation requise » (jamais une erreur), les capacités honnêtes et l'absence
de demande d'autorisation lors d'une simple lecture d'état."""

import asyncio
import json

import pytest

from app.devices.android import AndroidDriver
from app.devices.base import DeviceError


class FakeBridge:
    def __init__(self):
        self.calls = []
        self.bluetooth = True
        self.permission = False
        self.responses = {}

    def hasBluetooth(self, ctx):
        return self.bluetooth

    def audioList(self, ctx):
        return json.dumps({"supported": True, "devices": [{"id": "7", "name": "Haut-parleur", "kind": "internal", "is_default": True}], "default_id": "7"})

    def audioSetVolume(self, ctx, volume, muted):
        self.calls.append(("volume", volume, muted))
        return json.dumps({"ok": True})

    def bluetoothStatus(self, ctx):
        self.calls.append(("status",))
        if not self.permission:
            return json.dumps({"error": "permission_required", "message": "Autorisez Appareils à proximité"})
        return json.dumps({"supported": True, "powered": True, "discovering": False, "devices": [], "pending_pairing": None, "pairing": None})

    def bluetoothRequestPermission(self, ctx):
        self.calls.append(("request_permission",))
        return json.dumps({"error": "permission_required", "message": "boîte de dialogue affichée"})

    def bluetoothRequestEnable(self, ctx):
        self.calls.append(("enable",))
        return json.dumps({"ok": True})

    def bluetoothScan(self, ctx, on):
        self.calls.append(("scan", on))
        return self.responses.get("scan", json.dumps({"ok": True}))

    def bluetoothPair(self, ctx, address):
        self.calls.append(("pair", address))
        return json.dumps({"ok": True})

    def wifiStatus(self, ctx):
        return json.dumps({"supported": True, "enabled": True, "interface": "wlan0", "state": "connected", "current": {"ssid": None, "signal": 80, "ip": "192.168.1.9"}, "networks": [], "known": [], "read_only": True})

    def openSettings(self, ctx, target):
        self.calls.append(("settings", target))
        return json.dumps({"ok": True})


@pytest.fixture()
def bridge():
    return FakeBridge()


def make(bridge):
    return AndroidDriver(bridge_factory=lambda: (bridge, object()))


def run(coro):
    return asyncio.run(coro)


def test_capabilities_are_honest_about_android_limits(bridge):
    caps = run(make(bridge).capabilities())
    assert caps["audio_list"]["supported"] and caps["audio_set_volume"]["supported"] and caps["wifi_status"]["supported"]
    assert caps["system_settings"]["supported"]
    for key in ("audio_set_default", "bluetooth_connect", "bluetooth_forget", "wifi_connect", "wifi_scan", "wifi_forget", "wifi_power"):
        assert not caps[key]["supported"] and caps[key]["reason"], key
    bridge.bluetooth = False
    caps = run(make(bridge).capabilities())
    assert not caps["bluetooth_pair"]["supported"] and "Bluetooth" in caps["bluetooth_pair"]["reason"]


def test_bridge_unavailable_is_reported_not_raised():
    def broken():
        raise RuntimeError("pas de Chaquopy")

    caps = run(AndroidDriver(bridge_factory=broken).capabilities())
    assert all(not c["supported"] for c in caps.values())


def test_status_without_permission_is_a_state_and_never_prompts(bridge):
    status = run(make(bridge).bluetooth_status())
    assert status["supported"] and status["permission_required"] is True
    assert ("request_permission",) not in bridge.calls  # lecture d'état : jamais de boîte de dialogue
    bridge.permission = True
    assert "permission_required" not in run(make(bridge).bluetooth_status())


def test_explicit_permission_request_is_expected_to_report_pending(bridge):
    run(make(bridge).bluetooth_request_permission())
    assert ("request_permission",) in bridge.calls


def test_error_codes_map_to_http_statuses(bridge):
    bridge.responses["scan"] = json.dumps({"error": "permission_required", "message": "Autorisez"})
    with pytest.raises(DeviceError) as exc:
        run(make(bridge).bluetooth_scan(True))
    assert (exc.value.code, exc.value.status) == ("permission_required", 409)
    bridge.responses["scan"] = json.dumps({"error": "bt_failed", "message": "boum"})
    with pytest.raises(DeviceError) as exc:
        run(make(bridge).bluetooth_scan(True))
    assert exc.value.status == 502


def test_java_exceptions_never_escape(bridge):
    def boom(ctx):
        raise RuntimeError("java.lang.IllegalStateException")

    bridge.audioList = boom
    with pytest.raises(DeviceError) as exc:
        run(make(bridge).audio_list())
    assert exc.value.code == "bridge_error"


def test_actions_and_unsupported_power_off(bridge):
    driver = make(bridge)
    run(driver.audio_set_volume("7", 0.5, None))
    run(driver.bluetooth_set_power(True))
    run(driver.bluetooth_pair("AA:BB:CC:DD:EE:FF"))
    run(driver.open_system_settings("wifi"))
    assert ("volume", 0.5, -1) in bridge.calls and ("enable",) in bridge.calls and ("settings", "wifi") in bridge.calls
    with pytest.raises(DeviceError) as exc:
        run(driver.bluetooth_set_power(False))
    assert exc.value.status == 501
    assert run(driver.wifi_status())["read_only"] is True
