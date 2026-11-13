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


def test_old_zeroconf_without_address_resolver_publishes_the_default_name(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def old_zeroconf(name, *args, **kwargs):
        if name == "zeroconf" and "AddressResolverIPv4" in (args[2] if len(args) > 2 and args[2] else ()):
            raise ImportError("cannot import name 'AddressResolverIPv4' from 'zeroconf'")
        return real_import(name, *args, **kwargs)

    monkeypatch.undo()
    monkeypatch.setattr(builtins, "__import__", old_zeroconf)
    assert mdns._held_by_other(MagicMock(), "bobine", "10.0.0.5") is False


def test_update_keeps_the_instance_name_chosen_at_registration(monkeypatch):
    zc = MagicMock()
    zc.register_service.side_effect = lambda info, **kwargs: setattr(info, "name", "Bobine-2._http._tcp.local.")
    ips = iter(["10.0.0.5", "10.0.0.9"])
    monkeypatch.setattr(mdns, "_local_ip", lambda: next(ips))
    mdns._register_or_update(zc, 1903)
    mdns._register_or_update(zc, 1903)
    assert zc.update_service.call_args.args[0].name == "Bobine-2._http._tcp.local."


def test_socket_failure_is_reported_then_retried(monkeypatch):
    import zeroconf

    states = []
    attempts = iter([OSError("pas d'interface multicast"), MagicMock()])

    def build():
        outcome = next(attempts)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def wait(delay):
        states.append(mdns.get_status()["state"])
        return len(states) > 1

    monkeypatch.setattr(zeroconf, "Zeroconf", build)
    monkeypatch.setattr(mdns, "_local_ip", lambda: "10.0.0.5")
    monkeypatch.setattr(mdns._stop_event, "wait", wait)
    mdns._run_loop(1903)
    assert states == ["failed", "ok"]


def test_stop_closes_the_socket_even_when_unregistering_fails():
    zc = MagicMock()
    zc.unregister_service.side_effect = RuntimeError("boucle fermee")
    mdns._zeroconf, mdns._service_info = zc, MagicMock()
    mdns.stop_mdns_responder()
    zc.close.assert_called_once()
