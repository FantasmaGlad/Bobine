from unittest.mock import MagicMock

import pytest

from app.utils import deployment
from app.utils import mdns


@pytest.fixture(autouse=True)
def _reset_mdns_state(monkeypatch):
    saved_status = dict(mdns._status)
    monkeypatch.setattr(mdns, "_held_by_other", lambda zc, host, ip: False)
    monkeypatch.delenv("BOBINE_MDNS", raising=False)
    mdns._stop_event.clear()
    yield
    mdns._hostname = mdns.MDNS_HOSTNAME
    mdns._status.clear()
    mdns._status.update(saved_status)
    mdns._service_info = None
    mdns._last_announced_ip = None
    mdns._zeroconf = None


def test_should_self_publish_false_on_headless(monkeypatch):
    monkeypatch.setattr(deployment, "get_deployment_profile", lambda: "linux-headless")
    assert mdns._should_self_publish() is False


def test_should_self_publish_false_on_desktop_with_native_avahi(monkeypatch):
    monkeypatch.setattr(deployment, "get_deployment_profile", lambda: "linux-desktop")
    monkeypatch.setattr(mdns, "_avahi_daemon_active", lambda: True)
    assert mdns._should_self_publish() is False


def test_should_self_publish_true_on_desktop_without_native_avahi(monkeypatch):
    monkeypatch.setattr(deployment, "get_deployment_profile", lambda: "linux-desktop")
    monkeypatch.setattr(mdns, "_avahi_daemon_active", lambda: False)
    assert mdns._should_self_publish() is True


def test_should_self_publish_true_on_windows(monkeypatch):
    monkeypatch.setattr(deployment, "get_deployment_profile", lambda: "windows")
    assert mdns._should_self_publish() is True


def test_register_or_update_registers_once_then_updates_on_ip_change(monkeypatch):
    zc = MagicMock()
    ips = iter(["10.0.0.5", "10.0.0.5", "10.0.0.9"])
    monkeypatch.setattr(mdns, "_local_ip", lambda: next(ips))

    first_ip = mdns._register_or_update(zc, 8000)
    assert first_ip == "10.0.0.5"
    zc.register_service.assert_called_once()
    zc.update_service.assert_not_called()

    second_ip = mdns._register_or_update(zc, 8000)
    assert second_ip == "10.0.0.5"
    zc.register_service.assert_called_once()
    zc.update_service.assert_not_called()

    third_ip = mdns._register_or_update(zc, 8000)
    assert third_ip == "10.0.0.9"
    zc.register_service.assert_called_once()
    zc.update_service.assert_called_once()


def test_register_or_update_raises_without_local_ip(monkeypatch):
    monkeypatch.setattr(mdns, "_local_ip", lambda: None)
    with pytest.raises(RuntimeError):
        mdns._register_or_update(MagicMock(), 8000)


def test_get_status_reflects_set_status():
    mdns._set_status("failed", "boom")
    assert mdns.get_status() == {"state": "failed", "detail": "boom", "host": "bobine.local"}

    mdns._set_status("ok")
    assert mdns.get_status() == {"state": "ok", "detail": None, "host": "bobine.local"}


def test_free_hostname_skips_names_held_by_another_machine(monkeypatch):
    held = {"bobine", "bobine-2"}
    monkeypatch.setattr(mdns, "_held_by_other", lambda zc, host, ip: host in held)
    assert mdns._free_hostname(MagicMock(), "10.0.0.5") == "bobine-3"


def test_register_publishes_the_free_hostname(monkeypatch):
    zc = MagicMock()
    monkeypatch.setattr(mdns, "_local_ip", lambda: "10.0.0.5")
    monkeypatch.setattr(mdns, "_held_by_other", lambda zc, host, ip: host == "bobine")
    mdns._register_or_update(zc, 1903)
    info = zc.register_service.call_args.args[0]
    assert info.server == "bobine-2.local."
    assert mdns.get_status()["host"] == "bobine-2.local"


def test_environment_switch_disables_the_responder(monkeypatch):
    monkeypatch.setenv("BOBINE_MDNS", "0")
    monkeypatch.setattr(deployment, "get_deployment_profile", lambda: "windows")
    assert mdns._should_self_publish() is False
    mdns.start_mdns_responder(1903)
    assert mdns.get_status()["state"] == "disabled"
