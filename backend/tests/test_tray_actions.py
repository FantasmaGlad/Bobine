"""Actions rapides de la barre système : états, pause et reprise par sortie, arrêt de toute la diffusion."""
import urllib.error

import pytest

from app.desktop import tray_actions
from app.desktop.tray_actions import Controls


class Backend:
    """Faux backend : état par sortie, journal des appels, pannes réglables."""

    def __init__(self, states=None):
        self.states = {("playback", "cable"): "playing", ("playback", "network"): "paused",
                       ("radio", "cable"): "waiting", ("radio", "network"): "playing", **(states or {})}
        self.calls = []
        self.down = False
        self.refused = set()

    def __call__(self, method, url, timeout):
        if self.down:
            raise urllib.error.URLError("refusé")
        self.calls.append((method, url.replace("http://x", "")))
        path = url.replace("http://x", "")
        if method == "GET":
            kind = "playback" if path.startswith("/api/playback") else "radio"
            target = path.rsplit("=", 1)[1].removeprefix("radio_")
            return {"state": self.states[(kind, target)]}
        if path in self.refused:
            raise urllib.error.HTTPError(url, 409, "verrouillé", {}, None)
        return {"state": {"state": "ok"}}


@pytest.fixture()
def backend():
    return Backend()


def controls(backend, clock=lambda: 0.0):
    return Controls(lambda: "http://x", backend, clock)


def test_labels_show_state_and_the_next_action(backend):
    c = controls(backend)
    assert c.label("playback", "cable", "Câblé") == "Câblé : lecture — Pause"
    assert c.label("playback", "network", "Réseau") == "Réseau : en pause — Reprendre"
    assert c.label("radio", "cable", "Radio câblée") == "Radio câblée : en attente"


def test_offline_backend(backend):
    backend.down = True
    c = controls(backend)
    assert c.label("playback", "cable", "Câblé") == "Câblé : hors ligne"
    assert c.next_action(c.states()[("playback", "cable")]) is None
    assert c.toggle("playback", "cable") is False and c.stop_all() == 0


def test_toggle_pauses_what_plays_and_resumes_what_is_paused(backend):
    c = controls(backend)
    assert c.toggle("playback", "cable") and backend.calls[-1] == ("POST", "/api/playback/cable/pause")
    assert c.toggle("playback", "network") and backend.calls[-1] == ("POST", "/api/playback/network/play")
    assert c.toggle("radio", "network") and backend.calls[-1] == ("POST", "/api/radio/network/pause")


def test_toggle_does_nothing_while_waiting(backend):
    c = controls(backend)
    assert c.toggle("radio", "cable") is False
    assert not [call for call in backend.calls if call[0] == "POST"]


def test_stop_all_stops_the_four_outputs_even_if_one_is_refused(backend):
    backend.refused.add("/api/playback/cable/stop")
    c = controls(backend)
    assert c.stop_all() == 3
    stops = sorted(url for method, url in backend.calls if method == "POST")
    assert stops == ["/api/playback/cable/stop", "/api/playback/network/stop", "/api/radio/cable/stop", "/api/radio/network/stop"]


def test_states_are_cached_briefly_and_refreshed_after_an_action(backend):
    now = [0.0]
    c = controls(backend, lambda: now[0])
    c.states(); c.states(); c.label("playback", "cable", "Câblé")
    assert len([call for call in backend.calls if call[0] == "GET"]) == 4  # une lecture par sortie, une seule fois
    now[0] = 5.0
    c.states()
    assert len([call for call in backend.calls if call[0] == "GET"]) == 8
    c.toggle("playback", "cable")
    backend.states[("playback", "cable")] = "paused"
    assert c.label("playback", "cable", "Câblé") == "Câblé : en pause — Reprendre"


def test_unknown_state_is_shown_as_is(backend):
    backend.states[("playback", "cable")] = "buffering"
    assert controls(backend).label("playback", "cable", "Câblé") == "Câblé : buffering"


def test_routes_are_the_ones_of_the_rest_facade():
    assert tray_actions._action_path("radio", "cable", "stop") == "/api/radio/cable/stop"
    assert tray_actions._state_path("radio", "network") == "/api/radio/state?channel=radio_network"
    assert tray_actions._state_path("playback", "cable") == "/api/playback/state?channel=cable"
