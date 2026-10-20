"""Détail d'une sortie audio : analyse (pw-dump), balance gauche/droite, son de test, profil, alias et masquage."""

import asyncio
import io
import os
import wave

os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_database.db"
os.environ["BOBINE_MEDIA_DIR"] = "data/test_videos"
os.environ["BOBINE_WATCH_DIR"] = "data/test_watched"
os.environ["BOBINE_THUMBNAILS_DIR"] = "data/test_thumbnails"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import SessionLocal, init_db  # noqa: E402
from app.devices.base import DeviceDriver, DeviceError  # noqa: E402
from app.devices.linux import LinuxDriver  # noqa: E402
from app.devices.linux_parse import (  # noqa: E402
    balance_from_channel_volumes,
    channel_volumes_for_balance,
    find_sink_node,
    parse_audio_details,
    tone_wav_bytes,
)
from app.devices.service import service  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Setting  # noqa: E402

SINK = "alsa_output.speaker"
DUMP = [
    {"id": 52, "type": "PipeWire:Interface:Device", "info": {
        "props": {"device.description": "Ryzen HD Audio", "device.bus": "pci", "device.api": "alsa"},
        "params": {
            "Profile": [{"index": 2, "name": "HiFi", "description": "Haut-parleurs"}],
            "EnumProfile": [
                {"index": 0, "name": "off", "description": "Désactivé", "available": "yes"},
                {"index": 1, "name": "HiFiH", "description": "Casque", "available": "no"},
                {"index": 2, "name": "HiFi", "description": "Haut-parleurs", "available": "yes"},
                {"index": 3, "name": "pro", "description": "Pro Audio", "available": "unknown"},
            ],
        }}},
    {"id": 60, "type": "PipeWire:Interface:Node", "info": {
        "state": "running",
        "props": {"media.class": "Audio/Sink", "node.name": SINK, "node.description": "Haut-parleurs", "device.id": 52,
                  "audio.channels": 2, "audio.position": "[ FL, FR ]", "node.latency": "1024/48000", "api.alsa.card.name": "HD-Audio"},
        "params": {
            "Props": [{"volume": 1.0, "mute": False, "channelVolumes": [0.097331, 0.097331], "channelMap": ["FL", "FR"]}],
            "Format": [{"rate": 48000, "format": "S32LE", "channels": 2}],
        }}},
    {"id": 61, "type": "PipeWire:Interface:Node", "info": {"props": {"media.class": "Audio/Source", "node.name": "micro"}}},
]


def test_parse_audio_details_reads_node_card_profile_and_balance():
    d = parse_audio_details(DUMP, SINK)
    assert d["state"] == "running" and d["channels"] == 2 and d["channel_map"] == ["FL", "FR"]
    assert d["sample_rate"] == 48000 and d["format"] == "S32LE" and d["latency_ms"] == 21.3
    assert d["card"] == "HD-Audio" and d["bus"] == "pci"
    assert d["profile"]["index"] == 2 and d["profile"]["active"]
    assert [p["index"] for p in d["profiles"]] == [1, 2, 3]  # « off » n'est pas proposé
    assert [p["available"] for p in d["profiles"]] == [False, True, True]
    assert d["balance"] == 0.0 and d["level"] == pytest.approx(0.46, abs=0.001)
    assert parse_audio_details(DUMP, "absente") is None
    assert find_sink_node(DUMP, "micro") is None  # une source n'est pas une sortie


def test_balance_math_roundtrip_and_level_preserved():
    base = [0.097331, 0.097331]
    for b in (-1.0, -0.5, 0.0, 0.25, 1.0):
        volumes = channel_volumes_for_balance(base, b)
        assert balance_from_channel_volumes(volumes) == pytest.approx(b, abs=0.01)
        assert max(v ** (1 / 3) for v in volumes) == pytest.approx(0.46, abs=0.001)  # niveau maître conservé
    assert channel_volumes_for_balance(base, -1.0)[1] == 0.0  # tout à gauche : droite coupée
    assert channel_volumes_for_balance(base, 9)[0] == 0.0  # borné
    assert balance_from_channel_volumes([0.1, 0.1, 0.1]) is None  # pas de balance hors stéréo
    assert balance_from_channel_volumes([0.0, 0.0]) == 0.0


def test_tone_wav_is_stereo_short_quiet_and_silences_the_other_channel():
    for channel, loud in (("left", 0), ("right", 1), ("both", None)):
        with wave.open(io.BytesIO(tone_wav_bytes(channel))) as wav:
            assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) == (2, 2, 48000)
            assert wav.getnframes() / wav.getframerate() == pytest.approx(1.5, abs=0.01)
            raw = wav.readframes(wav.getnframes())
        import struct
        samples = struct.unpack("<" + "h" * (len(raw) // 2), raw)
        left, right = samples[0::2], samples[1::2]
        assert max(abs(s) for s in left + right) < 32767 * 0.25  # plafond d'amplitude
        if loud == 0:
            assert max(abs(s) for s in right) == 0 and max(abs(s) for s in left) > 1000
        elif loud == 1:
            assert max(abs(s) for s in left) == 0 and max(abs(s) for s in right) > 1000
        else:
            assert max(abs(s) for s in left) > 1000 and max(abs(s) for s in right) > 1000
        assert left[0] == 0 and left[-1] == 0  # fondus : pas de claquement
    with pytest.raises(ValueError):
        tone_wav_bytes("haut")


class FakeRunner:
    def __init__(self):
        self.calls = []
        self.fail = False

    async def __call__(self, *args, timeout=10.0, stdin=None):
        self.calls.append(args)
        if args[0] == "pw-dump":
            import json
            return 0, json.dumps(DUMP), ""
        if self.fail:
            return 1, "", "refusé"
        if args[0] == "pw-play":
            await asyncio.sleep(0.15)
        return 0, "", ""


def test_linux_driver_balance_profile_and_tone(monkeypatch):
    runner = FakeRunner()
    driver = LinuxDriver(runner=runner)
    monkeypatch.setattr("app.devices.linux.shutil.which", lambda tool: "/usr/bin/" + tool)

    async def scenario():
        await driver.audio_set_balance(SINK, -1.0)
        cmd = next(c for c in runner.calls if c[0] == "pw-cli")
        assert cmd[:4] == ("pw-cli", "set-param", "60", "Props") and "channelVolumes: [0.097331, 0.000000]" in cmd[4]
        await driver.audio_set_profile(SINK, 3)
        assert ("wpctl", "set-profile", "52", "3") in runner.calls
        for bad in (1, 99, 0):  # indisponible, inexistant, « off »
            with pytest.raises(DeviceError) as exc:
                await driver.audio_set_profile(SINK, bad)
            assert exc.value.code == "bad_profile"
        with pytest.raises(DeviceError) as exc:
            await driver.audio_test_tone(SINK, "haut")
        assert exc.value.code == "bad_channel"
        # Un seul son de test à la fois, jamais deux superposés.
        first = asyncio.create_task(driver.audio_test_tone(SINK, "left"))
        await asyncio.sleep(0.05)
        with pytest.raises(DeviceError) as busy:
            await driver.audio_test_tone(SINK, "right")
        assert busy.value.code == "busy" and busy.value.status == 409
        await first
        play = next(c for c in runner.calls if c[0] == "pw-play")
        assert play[1:5] == ("--target", SINK, "--volume", "0.5")
        with pytest.raises(DeviceError) as gone:
            await driver.audio_set_balance("absente", 0.0)
        assert gone.value.status == 404
        runner.fail = True
        with pytest.raises(DeviceError) as failed:
            await driver.audio_set_balance(SINK, 0.2)
        assert failed.value.code == "audio_failed"

    asyncio.run(scenario())


def test_linux_driver_reports_missing_tools(monkeypatch):
    driver = LinuxDriver(runner=FakeRunner())
    monkeypatch.setattr("app.devices.linux.shutil.which", lambda tool: None)

    async def scenario():
        for call in (driver.audio_set_balance(SINK, 0.0), driver.audio_test_tone(SINK, "both")):
            with pytest.raises(DeviceError) as exc:
                await call
            assert exc.value.code == "tool_missing"

    asyncio.run(scenario())


# ---------------------------------------------------------------------------
# Routes : alias, masquage, validations
# ---------------------------------------------------------------------------


class FakeAudioDriver(DeviceDriver):
    name = "fake"

    def __init__(self):
        super().__init__()
        self.calls = []

    async def capabilities(self):
        return {}

    async def audio_list(self):
        return {"supported": True, "devices": [{"id": "a", "name": "Haut-parleurs"}, {"id": "b", "name": "HDMI"}], "default_id": "a"}

    async def audio_details(self, device_id):
        return {"supported": True, "id": device_id, "name": "Détail"}

    async def audio_set_balance(self, device_id, balance):
        self.calls.append(("balance", device_id, balance))

    async def audio_test_tone(self, device_id, channel):
        self.calls.append(("tone", device_id, channel))

    async def bluetooth_status(self):
        return {"supported": False, "reason": "x"}

    async def wifi_status(self):
        return {"supported": False, "reason": "x"}


@pytest.fixture()
def api(monkeypatch):
    init_db()
    driver = FakeAudioDriver()
    service.set_driver(driver)
    monkeypatch.setattr("app.routers.devices.is_local_request", lambda request: True)
    with SessionLocal() as db:
        db.query(Setting).filter(Setting.key.in_(("devices_enabled", "devices_audio_meta"))).delete(synchronize_session=False)
        db.add(Setting(key="devices_enabled", value="true"))
        db.commit()
    yield TestClient(app), driver
    service.set_driver(None)
    with SessionLocal() as db:
        db.query(Setting).filter(Setting.key.in_(("devices_enabled", "devices_audio_meta"))).delete(synchronize_session=False)
        db.commit()


def test_balance_and_tone_validation_and_dispatch(api):
    client, driver = api
    assert client.post("/api/devices/audio/balance", json={"id": "a", "balance": 1.5}).json()["detail"]["code"] == "bad_balance"
    assert client.post("/api/devices/audio/test", json={"id": "a", "channel": "centre"}).json()["detail"]["code"] == "bad_channel"
    assert client.post("/api/devices/audio/balance", json={"id": "a", "balance": -0.4}).status_code == 200
    assert client.post("/api/devices/audio/test", json={"id": "a", "channel": "left"}).status_code == 200
    assert driver.calls == [("balance", "a", -0.4), ("tone", "a", "left")]
    unsupported = client.post("/api/devices/audio/profile", json={"id": "a", "index": 1})
    assert unsupported.status_code == 501 and unsupported.json()["detail"]["code"] == "unsupported"


def test_alias_and_hidden_are_merged_into_listing_and_details(api):
    client, _ = api
    assert client.put("/api/devices/audio/meta", json={"id": "a", "alias": "  Salle principale ", "hidden": False}).json() == {"ok": True, "alias": "Salle principale", "hidden": False}
    assert client.put("/api/devices/audio/meta", json={"id": "b", "hidden": True}).json()["hidden"] is True
    listing = client.get("/api/devices/audio").json()["devices"]
    assert [(d["id"], d["alias"], d["hidden"]) for d in listing] == [("a", "Salle principale", False), ("b", None, True)]
    assert client.get("/api/devices/audio/details", params={"id": "a"}).json()["alias"] == "Salle principale"
    # Effacer l'alias et réafficher supprime l'entrée.
    client.put("/api/devices/audio/meta", json={"id": "a", "alias": ""})
    client.put("/api/devices/audio/meta", json={"id": "b", "hidden": False})
    with SessionLocal() as db:
        assert db.query(Setting).filter(Setting.key == "devices_audio_meta").first() is None


def test_alias_validation_and_limits(api):
    client, _ = api
    for bad in ("x" * 61, "a\nb"):
        assert client.put("/api/devices/audio/meta", json={"id": "a", "alias": bad}).json()["detail"]["code"] == "bad_alias"
    assert client.put("/api/devices/audio/meta", json={"id": "", "alias": "x"}).json()["detail"]["code"] == "bad_id"
    for i in range(200):
        assert client.put("/api/devices/audio/meta", json={"id": f"dev{i}", "hidden": True}).status_code == 200
    assert client.put("/api/devices/audio/meta", json={"id": "autre", "hidden": True}).json()["detail"]["code"] == "too_many"


def test_default_driver_methods_degrade_gracefully():
    from app.devices.base import NullDriver

    driver = NullDriver("non")

    async def scenario():
        assert (await driver.audio_details("x"))["supported"] is False
        for call in (driver.audio_set_balance("x", 0), driver.audio_test_tone("x", "both"), driver.audio_set_profile("x", 1)):
            with pytest.raises(DeviceError) as exc:
                await call
            assert exc.value.status == 501

    asyncio.run(scenario())
