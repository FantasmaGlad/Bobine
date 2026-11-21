import asyncio
import pytest
from app.devices.base import CAPABILITY_KEYS, DeviceError, NullDriver
from app.devices.linux.driver import LinuxDriver
from app.devices.linux.parse.audio import choose_browser_stream, parse_output_streams
from devices_routing_support import _stream, _sink, _link, FakePipeWire, _driver, _no_sleep, _async_value


def test_analyse_des_flux_reconnait_navigateurs_etat_et_sortie_liee():
    dump = [_sink(10, "alsa_output.speaker"), _sink(11, "bluez_output.x"), _stream(70, "chromium", "Chromium"), _stream(71, "mpv", "mpv"),
            _stream(72, "firefox", "Firefox", state="idle"), _link(70, 10), _link(71, 11)]
    streams = {s["id"]: s for s in parse_output_streams(dump)}
    assert streams[70]["browser"] and streams[70]["sink"] == "alsa_output.speaker" and streams[70]["state"] == "running"
    assert not streams[71]["browser"] and streams[71]["sink"] == "bluez_output.x"
    assert streams[72]["browser"] and streams[72]["sink"] is None


def test_choix_du_flux_jamais_de_devinette():
    mpv = parse_output_streams([_stream(1, "mpv", "mpv")])
    assert choose_browser_stream(mpv) == ("none", None)
    one = parse_output_streams([_stream(1, "chromium", "Chromium"), _stream(2, "chromium", "Chromium", state="idle")])
    verdict, stream = choose_browser_stream(one)
    assert verdict == "one" and stream["id"] == 1
    two = parse_output_streams([_stream(1, "chromium", "Chromium"), _stream(2, "firefox", "Firefox")])
    assert choose_browser_stream(two) == ("ambiguous", None)


def test_deplacement_verifie_du_flux_unique(pw_tools, monkeypatch):
    monkeypatch.setattr("app.devices.linux.audio_routing.asyncio.sleep", _no_sleep)
    driver, pw = _driver({70: {"binary": "chromium", "app": "Chromium", "state": "running", "sink": None}})
    result = asyncio.run(driver.audio_route_stream("bluez_output.88_92_CC_9C_41_0E.1"))
    assert result["status"] == "moved" and result["app"] == "Chromium"
    assert ("pw-metadata", "-n", "default", "70", "target.object", "bluez_output.88_92_CC_9C_41_0E.1", "Spa:String") in pw.calls
    again = asyncio.run(driver.audio_route_stream("bluez_output.88_92_CC_9C_41_0E.1"))
    assert again["status"] == "unchanged"
    released = asyncio.run(driver.audio_route_stream(None))
    assert released["status"] == "released" and pw.streams[70]["sink"] is None
    assert asyncio.run(driver.audio_route_stream(None))["status"] == "unchanged"


def test_retour_arriere_si_le_flux_ne_rejoint_pas_la_sortie(pw_tools, monkeypatch):
    monkeypatch.setattr("app.devices.linux.audio_routing.asyncio.sleep", _no_sleep)
    driver, pw = _driver({70: {"binary": "chromium", "app": "Chromium", "state": "running", "sink": None}}, follow=False)
    result = asyncio.run(driver.audio_route_stream("alsa_output.hdmi"))
    assert result["status"] == "failed"
    assert any("-d" in call for call in pw.calls)


def test_aucun_deplacement_si_flux_ambigu_ou_absent(pw_tools, monkeypatch):
    monkeypatch.setattr("app.devices.linux.audio_routing.asyncio.sleep", _no_sleep)
    two = {70: {"binary": "chromium", "app": "Chromium", "state": "running", "sink": None},
           71: {"binary": "firefox", "app": "Firefox", "state": "running", "sink": None}}
    driver, pw = _driver(two)
    assert asyncio.run(driver.audio_route_stream("alsa_output.hdmi"))["status"] == "ambiguous"
    assert not any(call[0] == "pw-metadata" for call in pw.calls)
    driver, pw = _driver({1: {"binary": "mpv", "app": "mpv", "state": "running", "sink": None}})
    assert asyncio.run(driver.audio_route_stream("alsa_output.hdmi"))["status"] == "no_stream"


def test_sortie_disparue_ou_outil_absent_sont_des_erreurs_structurees(pw_tools, monkeypatch):
    driver, _ = _driver({70: {"binary": "chromium", "app": "Chromium", "state": "running", "sink": None}})
    with pytest.raises(DeviceError) as gone:
        asyncio.run(driver.audio_route_stream("alsa_output.inconnue"))
    assert gone.value.code == "not_found" and gone.value.status == 404
    monkeypatch.setattr("app.devices.linux.driver.shutil.which", lambda name: None if name == "pw-metadata" else f"/usr/bin/{name}")
    with pytest.raises(DeviceError) as missing:
        asyncio.run(driver.audio_route_stream("alsa_output.hdmi"))
    assert missing.value.code == "tool_missing"


def test_capacite_declaree_selon_les_outils(monkeypatch):
    async def run(which):
        monkeypatch.setattr("app.devices.linux.driver.shutil.which", which)
        driver = LinuxDriver(runner=FakePipeWire({}))
        driver._probe_bluetooth = _async_value("pas de Bluetooth")
        driver._probe_wifi = _async_value("pas de Wi-Fi")
        return await driver.capabilities()

    caps = asyncio.run(run(lambda name: f"/usr/bin/{name}"))
    assert caps["audio_route_stream"] == {"supported": True}
    caps = asyncio.run(run(lambda name: None if name == "pw-metadata" else f"/usr/bin/{name}"))
    assert caps["audio_route_stream"]["supported"] is False and "pw-metadata" in caps["audio_route_stream"]["reason"]
    caps = asyncio.run(run(lambda name: None))
    assert caps["audio_route_stream"]["supported"] is False


def test_tous_les_pilotes_declarent_la_capacite():
    assert "audio_route_stream" in CAPABILITY_KEYS
    caps = asyncio.run(NullDriver("raison").capabilities())
    assert caps["audio_route_stream"] == {"supported": False, "reason": "raison"}
    with pytest.raises(DeviceError) as exc:
        asyncio.run(NullDriver().audio_route_stream("x"))
    assert exc.value.status == 501
