"""Choix de l'adresse du réseau local : jamais un VPN, un conteneur ni le réseau mobile."""

import pytest

from app.utils import network


def _fake(monkeypatch, pairs, env=None):
    monkeypatch.setattr(network, "_enumerate_ipv4", lambda: pairs)
    monkeypatch.setattr(network, "_route_ip", lambda: "10.2.0.2")
    if env is None:
        monkeypatch.delenv(network.LAN_IP_ENV, raising=False)
    else:
        monkeypatch.setenv(network.LAN_IP_ENV, env)


def test_wifi_prefere_au_vpn_meme_si_le_vpn_porte_la_route(monkeypatch):
    _fake(monkeypatch, [("wg0", "10.2.0.2"), ("wlan0", "192.168.1.17"), ("lo", "127.0.0.1")])
    assert network.primary_lan_ip() == "192.168.1.17"


def test_ethernet_prefere_au_wifi(monkeypatch):
    _fake(monkeypatch, [("wlp3s0", "192.168.1.20"), ("enp2s0", "192.168.1.10")])
    assert network.primary_lan_ip() == "192.168.1.10"


@pytest.mark.parametrize(
    "name",
    ["tun0", "tailscale0", "docker0", "br-1a2b3c", "veth12", "rmnet_data0", "utun3", "ProtonVPN TUN", "vEthernet (WSL)", "virbr0", "zt5u4abc"],
)
def test_interfaces_virtuelles_ecartees(monkeypatch, name):
    _fake(monkeypatch, [(name, "172.17.0.1"), ("wlan0", "192.168.0.5")])
    assert network.primary_lan_ip() == "192.168.0.5"


def test_noms_windows_et_macos(monkeypatch):
    _fake(monkeypatch, [("Wi-Fi", "192.168.1.30"), ("Loopback Pseudo-Interface 1", "127.0.0.1")])
    assert network.primary_lan_ip() == "192.168.1.30"
    _fake(monkeypatch, [("en0", "192.168.1.40"), ("utun4", "100.100.1.2"), ("awdl0", "169.254.1.1")])
    assert network.primary_lan_ip() == "192.168.1.40"


def test_adresse_native_android_prioritaire(monkeypatch):
    _fake(monkeypatch, [("wlan0", "192.168.1.20"), ("rmnet0", "10.50.1.2")], env="192.168.1.77")
    assert network.primary_lan_ip() == "192.168.1.77"


def test_liens_locaux_et_bouclage_jamais_retenus(monkeypatch):
    _fake(monkeypatch, [("eth0", "169.254.7.7"), ("lo", "127.0.0.1")])
    assert network.lan_addresses() == []


def test_repli_sur_la_route_par_defaut_sans_candidat(monkeypatch):
    _fake(monkeypatch, [])
    assert network.primary_lan_ip() == "10.2.0.2"


def test_cgnat_en_dernier_choix(monkeypatch):
    _fake(monkeypatch, [("eth0", "100.72.1.2"), ("wlan0", "192.168.1.5")])
    assert network.primary_lan_ip() == "192.168.1.5"
