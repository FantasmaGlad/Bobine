import urllib.error

import pytest

from app.desktop import tray_actions
from app.desktop.tray_actions import Controls


class Backend:

    def __init__(self, states=None):
        self.states = {("playback", "cable"): "playing", ("playback", "network"): "paused",
                       ("playback", "network_2"): "idle", ("radio", "cable"): "waiting", ("radio", "network"): "playing", ("radio", "network_2"): "idle",
                       **(states or {})}
        self.calls = []
        self.down = False
        self.refused = set()

    def __call__(self, method, url, timeout):
        if self.down:
            raise urllib.error.URLError("refusé")
        path = url.replace("http://x", "")
        self.calls.append((method, path))
        if method == "GET":
            return [{"id": output, "playback": {"state": self.states[("playback", output)]}, "radio": {"state": self.states[("radio", output)]}}
                    for output in ("cable", "network", "network_2")]
        if path in self.refused:
            raise urllib.error.HTTPError(url, 409, "verrouillé", {}, None)
        return {"id": "cable"}


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
    assert c.toggle("playback", "cable") and backend.calls[-1] == ("POST", "/api/outputs/cable/playback/pause")
    assert c.toggle("playback", "network") and backend.calls[-1] == ("POST", "/api/outputs/network/playback/play")
    assert c.toggle("radio", "network") and backend.calls[-1] == ("POST", "/api/outputs/network/radio/pause")


def test_toggle_does_nothing_while_waiting(backend):
    c = controls(backend)
    assert c.toggle("radio", "cable") is False
    assert not [call for call in backend.calls if call[0] == "POST"]


def test_stop_all_stops_every_output_even_if_one_is_refused(backend):
    backend.refused.add("/api/outputs/cable/playback/stop")
    c = controls(backend)
    assert c.stop_all() == 5
    stops = sorted(url for method, url in backend.calls if method == "POST")
    assert stops == ["/api/outputs/cable/playback/stop", "/api/outputs/cable/radio/stop", "/api/outputs/network/playback/stop",
                     "/api/outputs/network/radio/stop", "/api/outputs/network_2/playback/stop", "/api/outputs/network_2/radio/stop"]


def test_states_are_cached_briefly_and_refreshed_after_an_action(backend):
    now = [0.0]
    c = controls(backend, lambda: now[0])
    c.states(); c.states(); c.label("playback", "cable", "Câblé")
    assert len([call for call in backend.calls if call[0] == "GET"]) == 1
    now[0] = 5.0
    c.states()
    assert len([call for call in backend.calls if call[0] == "GET"]) == 2
    c.toggle("playback", "cable")
    backend.states[("playback", "cable")] = "paused"
    assert c.label("playback", "cable", "Câblé") == "Câblé : en pause — Reprendre"


def test_unknown_state_is_shown_as_is(backend):
    backend.states[("playback", "cable")] = "buffering"
    assert controls(backend).label("playback", "cable", "Câblé") == "Câblé : buffering"


def test_routes_are_the_ones_of_the_rest_facade():
    assert tray_actions._action_path("radio", "cable", "stop") == "/api/outputs/cable/radio/stop"
    assert tray_actions.STATES_PATH == "/api/outputs"


def test_update_outcome_notification_is_recent_new_and_unacknowledged():
    from app.desktop.tray_actions import should_notify_update_outcome as notify

    done = {"step": "done", "started_at": 100.0, "updated_at": 110.0, "acknowledged_started_at": None}
    assert notify(done, None, now=120.0)
    assert not notify(done, 100.0, now=120.0)
    assert not notify({**done, "acknowledged_started_at": 100.0}, None, now=120.0)
    assert not notify(done, None, now=110.0 + 601)
    assert not notify({**done, "step": "installing"}, None, now=120.0)
