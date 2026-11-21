"""Appui des tests du routage audio : sorties types, PipeWire simulé, pilote et lecteurs simulés."""

import json
from app.database import SessionLocal
from app.devices.base import DeviceDriver
from app.devices.linux.driver import LinuxDriver
from app.devices.routing import (
    ROUTES_SETTING,
    describe_sink,
    save_routes,
)
from app.radio.manager import get_radio_manager


KEYS = (ROUTES_SETTING, "devices_audio_meta")


SPEAKER = {"id": "alsa_output.speaker", "name": "Haut-parleurs", "description": "Ryzen HD Audio", "kind": "internal", "is_default": True, "available": True}


JBL = {"id": "bluez_output.88_92_CC_9C_41_0E.1", "name": "JBL Live 770NC", "description": "JBL Live", "kind": "bluetooth", "is_default": False, "available": True}


HDMI = {"id": "alsa_output.hdmi", "name": "HDMI / DP", "description": "Écran HDMI", "kind": "hdmi", "is_default": False, "available": True}


def _stream(node_id, binary, app_name, state="running"):
    return {"id": node_id, "type": "PipeWire:Interface:Node", "info": {"state": state, "props": {
        "media.class": "Stream/Output/Audio", "node.name": f"{binary}-{node_id}", "application.name": app_name, "application.process.binary": binary}}}


def _sink(node_id, name):
    return {"id": node_id, "type": "PipeWire:Interface:Node", "info": {"props": {"media.class": "Audio/Sink", "node.name": name, "node.description": name}}}


def _link(out_id, in_id):
    return {"id": 900 + out_id, "type": "PipeWire:Interface:Link", "info": {"props": {"link.output.node": out_id, "link.input.node": in_id}}}


class FakePipeWire:

    def __init__(self, streams, follow=True):
        self.streams = streams
        self.follow = follow
        self.calls: list[tuple] = []
        self.default = "alsa_output.speaker"

    def dump(self):
        data = [_sink(10, "alsa_output.speaker"), _sink(11, "bluez_output.88_92_CC_9C_41_0E.1"), _sink(12, "alsa_output.hdmi")]
        ids = {"alsa_output.speaker": 10, "bluez_output.88_92_CC_9C_41_0E.1": 11, "alsa_output.hdmi": 12}
        for sid, s in self.streams.items():
            data.append(_stream(sid, s["binary"], s["app"], s["state"]))
            data.append(_link(sid, ids[s["sink"] or self.default]))
        return data

    async def __call__(self, *args, timeout=10.0, stdin=None):
        self.calls.append(args)
        if args[0] == "pw-dump":
            return 0, json.dumps(self.dump()), ""
        if args[0] == "wpctl":
            return 0, "Volume: 0.40", ""
        if args[0] == "pw-metadata":
            if "-d" in args:
                self.streams[int(args[args.index("-d") + 1])]["sink"] = None
            elif self.follow:
                self.streams[int(args[3])]["sink"] = args[5]
            return 0, "", ""
        return 1, "", "commande inconnue"


def _driver(streams, follow=True):
    pw = FakePipeWire(streams, follow)
    driver = LinuxDriver(runner=pw)
    return driver, pw


async def _no_sleep(_):
    return None


def _async_value(value):
    async def inner(*args, **kwargs):
        return value

    return inner


class RoutingDriver(DeviceDriver):
    name = "fake-routing"

    def __init__(self, sinks=None, route_cap=True):
        super().__init__()
        self.sinks = [dict(s) for s in (sinks if sinks is not None else [SPEAKER, JBL, HDMI])]
        self.route_cap = route_cap
        self.routed: list[str | None] = []
        self.result = {"status": "moved", "app": "Chromium"}

    async def capabilities(self):
        return {"audio_list": {"supported": True}, "audio_route_stream": {"supported": self.route_cap, "reason": "" if self.route_cap else "non"}}

    async def audio_list(self):
        return {"supported": True, "devices": self.sinks, "default_id": SPEAKER["id"]}

    async def audio_route_stream(self, sink_id):
        self.routed.append(sink_id)
        return {"status": "released"} if sink_id is None else dict(self.result)

    async def bluetooth_status(self):
        return {"supported": False}

    async def wifi_status(self):
        return {"supported": False}


class FakeSocket:
    def __init__(self, host="127.0.0.1"):
        self.client = type("C", (), {"host": host})()


def _reset_managers():
    for channel in ("radio_cable", "radio_network"):
        manager = get_radio_manager(channel)
        manager.state["route"] = None
        manager.state["playing"] = False


def _route(channel="radio_cable", sink=JBL, fallback="default"):
    with SessionLocal() as db:
        save_routes(db, {channel: describe_sink(sink) | {"fallback": fallback}})


def _add_player(channel, host="127.0.0.1", primary=True, status=None):
    from app.utils.ws_manager import manager as ws

    sock = FakeSocket(host)
    ws._kiosk_connections[channel].append(sock)
    ws._kiosk_channel[sock] = channel
    ws._kiosk_primary_status[sock] = primary
    if status:
        ws._route_reports[sock] = {"status": status}
    return sock


def _local(monkeypatch):
    monkeypatch.setattr("app.api.routes.devices.access.is_local_request", lambda request: True)


def _players(client, channel):
    view = client.get("/api/devices/routing").json()
    output = next(o for o in view["outputs"] if o["channel"] == channel)
    return [p["status"] for p in output["players"]]


def _wait_for(predicate, tries=60):
    import time

    for _ in range(tries):
        if predicate():
            return
        time.sleep(0.05)
    assert predicate()
