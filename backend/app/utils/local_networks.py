"""Réseaux de confiance de Bobine : l'unique liste, lue par la garde réseau."""
from __future__ import annotations

import ipaddress

FIREWALL_NETWORKS = (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "169.254.0.0/16", "100.64.0.0/10", "fc00::/7", "fe80::/10",
)
LOOPBACK_NETWORKS = ("127.0.0.0/8", "::1/128")

TRUSTED_NETWORKS = tuple(ipaddress.ip_network(n) for n in FIREWALL_NETWORKS + LOOPBACK_NETWORKS)
