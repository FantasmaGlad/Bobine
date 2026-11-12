"""Le pare-feu du système laisse-t-il le réseau local joindre Bobine ?"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from app.utils.local_networks import FIREWALL_NETWORKS

SOCKETFILTERFW = "/usr/libexec/ApplicationFirewall/socketfilterfw"
LOCAL_NETWORKS = ",".join(FIREWALL_NETWORKS)


def _run(command: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(command, capture_output=True, text=True, timeout=5)


def _windows_rule_is_usable(output: str, executable: str) -> bool:
    fields = {key.strip().lower(): value.strip() for key, _, value in (line.partition(":") for line in output.splitlines())}
    enabled = fields.get("enabled") or fields.get("activé")
    program = fields.get("program") or fields.get("programme")
    remote = fields.get("remoteip") or fields.get("adresse ip distante")
    if enabled and enabled.lower() in {"no", "non"}:
        return False
    if program and program.lower() not in {"any", "tout"} and program.lower() != executable.lower():
        return False
    return not (remote and remote.lower() in {"any", "tout"})


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
        rule = _run(["netsh", "advfirewall", "firewall", "show", "rule", "name=Bobine", "verbose"])
        if rule.returncode == 0 and _windows_rule_is_usable(rule.stdout, executable):
            return {"state": "allowed"}
        remedy = ('netsh advfirewall firewall add rule name="Bobine" dir=in action=allow '
                  f'program="{executable}" enable=yes profile=any remoteip={LOCAL_NETWORKS} '
                  "(invite de commandes en administrateur), ou réinstaller Bobine")
        return {"state": "rule_missing", "remedy": remedy}
    return {"state": "not_checked", "reason": "état lisible seulement en administrateur sur ce système"}
