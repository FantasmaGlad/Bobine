import re
from pathlib import Path

import pytest

from app.utils.local_networks import FIREWALL_NETWORKS
from app.api.network_guard import is_allowed_client

ROOT = Path(__file__).resolve().parents[2]


def test_configure_firewall_uses_the_shared_list():
    text = (ROOT / "packaging/linux/firewall/configure-firewall").read_text(encoding="utf-8")
    assert re.search(r'^networks="([^"]*)"', text, re.M).group(1).split() == list(FIREWALL_NETWORKS)


def test_windows_rule_uses_the_shared_list():
    text = (ROOT / "packaging/windows/bobine.iss").read_text(encoding="utf-8")
    rules = re.findall(r"remoteip=([^\s\"]+)", text)
    assert rules and all(rule.split(",") == list(FIREWALL_NETWORKS) for rule in rules)


@pytest.mark.parametrize("host", ["169.254.1.1", "127.0.0.2", "10.1.2.3", "100.64.0.1", "fd00::1"])
def test_listed_networks_are_trusted(host):
    assert is_allowed_client(host)


@pytest.mark.parametrize("host", ["0.0.0.1", "198.18.0.1", "2002::1", "2001:db8::1", "192.0.0.9", "224.0.0.1", "100.128.0.1", "::ffff:8.8.8.8"])
def test_everything_else_is_refused(host):
    assert not is_allowed_client(host)
