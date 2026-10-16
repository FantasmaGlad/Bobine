"""Non-regression de la consolidation mDNS : re-annonce sur changement
d'IP (zc.update_service, jamais un second register_service), detection
d'un avahi-daemon natif sur linux-desktop (evite un double repondeur
bobine.local), et etat expose par get_status()."""

from unittest.mock import MagicMock

import pytest

from app.utils import deployment
from app.utils import mdns


@pytest.fixture(autouse=True)
def _reset_mdns_state():
    saved_status = dict(mdns._status)
    yield
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

    # Meme IP qu'avant : ni un nouvel enregistrement ni une mise a jour.
    second_ip = mdns._register_or_update(zc, 8000)
    assert second_ip == "10.0.0.5"
    zc.register_service.assert_called_once()
    zc.update_service.assert_not_called()

    # IP changee (ex. renouvellement DHCP) : update_service, jamais un
    # second register_service pour le meme nom de service.
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
    assert mdns.get_status() == {"state": "failed", "detail": "boom"}

    mdns._set_status("ok")
    assert mdns.get_status() == {"state": "ok", "detail": None}
