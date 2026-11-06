"""Le pare-feu du système laisse-t-il le réseau local joindre Bobine ? Lecture seule, sans droits d'administrateur.

- macOS : le pare-feu applicatif (socketfilterfw) autorise ou bloque BobineBackend ; il ne se règle qu'en
  administrateur, d'où la commande exacte proposée en remède.
- Windows : l'installeur pose la règle « Bobine » (programme BobineBackend.exe, réseaux locaux et VPN) ; son absence
  coupe la télécommande et l'administration depuis un autre appareil.
- Linux : les paquets ouvrent le profil ufw ou le service firewalld aux réseaux locaux (configure-firewall) ; leur
  état ne se lit qu'en root, la sonde n'en dit rien. Android : pas de pare-feu entrant.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SOCKETFILTERFW = "/usr/libexec/ApplicationFirewall/socketfilterfw"
# Mêmes plages que packaging/linux/firewall/configure-firewall et la règle de packaging/windows/bobine.iss.
LOCAL_NETWORKS = "LocalSubnet,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,100.64.0.0/10,fc00::/7,fe80::/10"


def _run(command: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(command, capture_output=True, text=True, timeout=5)


def status(platform: str | None = None, executable: str | None = None) -> dict:
    """`state` : `allowed`, `blocked`, `rule_missing` ou `not_checked` ; `remedy` quand il faut agir."""
    platform = platform or sys.platform
    executable = executable or sys.executable
    frozen = getattr(sys, "frozen", False) or executable.endswith(("BobineBackend", "BobineBackend.exe"))
    if not frozen:
        return {"state": "not_checked", "reason": "installation de développement"}
    if platform == "darwin":
        if not Path(SOCKETFILTERFW).exists():
            return {"state": "not_checked", "reason": "socketfilterfw absent"}
        if "State = 0" in _run([SOCKETFILTERFW, "--getglobalstate"]).stdout:
            return {"state": "allowed", "reason": "pare-feu macOS désactivé"}
        block_all = "enabled" in _run([SOCKETFILTERFW, "--getblockall"]).stdout.lower()
        app = _run([SOCKETFILTERFW, "--getappblocked", executable]).stdout.lower()
        if block_all or "blocked" in app or "not part of the firewall" in app:
            remedy = (f'sudo {SOCKETFILTERFW} --add "{executable}" && sudo {SOCKETFILTERFW} --unblockapp "{executable}"'
                      + (f" && sudo {SOCKETFILTERFW} --setblockall off" if block_all else ""))
            return {"state": "blocked", "remedy": remedy}
        return {"state": "allowed"}
    if platform == "win32":
        if _run(["netsh", "advfirewall", "firewall", "show", "rule", "name=Bobine"]).returncode == 0:
            return {"state": "allowed"}
        remedy = ('netsh advfirewall firewall add rule name="Bobine" dir=in action=allow '
                  f'program="{executable}" enable=yes profile=any remoteip={LOCAL_NETWORKS} '
                  "(invite de commandes en administrateur), ou réinstaller Bobine")
        return {"state": "rule_missing", "remedy": remedy}
    return {"state": "not_checked", "reason": "état lisible seulement en administrateur sur ce système"}
