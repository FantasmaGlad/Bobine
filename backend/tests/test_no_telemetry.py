import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RUNTIME = [
    "backend/app", "frontend/src", "android/app/src/main", "devices/src", "media/src", "projector/src",
    "scripts/watchdog.sh", "packaging/firefox/policies.json",
]
URL = re.compile(r"https?://([A-Za-z0-9.-]+\.[A-Za-z]{2,})")

ALLOWED = {
    "api.github.com": "recherche de mise à jour",
    "github.com": "téléchargement d'une mise à jour, lien de release",
    "check.torproject.org": "bouton « Tester Tor », jamais automatique",
    "play.google.com": "ouverture de la fiche Play Store par l'utilisateur",
    "bobine.fit": "en-tête User-Agent, aucune requête",
}
IGNORED = ("www.w3.org", "schemas.android.com", "www.microsoft.com", "example.com", "example.org")


def _runtime_hosts() -> dict[str, list[str]]:
    files = subprocess.run(["git", "ls-files", "--", *RUNTIME], cwd=REPO, capture_output=True, text=True, check=True)
    hosts: dict[str, list[str]] = {}
    for name in files.stdout.split():
        if "/tests/" in name or name.endswith((".png", ".jpg", ".webp", ".ico", ".svg", ".woff2")):
            continue
        text = (REPO / name).read_text(encoding="utf-8", errors="ignore")
        for host in URL.findall(text):
            host = host.lower()
            if host.endswith(".onion") or host.endswith(".local") or host in IGNORED:
                continue
            hosts.setdefault(host, []).append(name)
    return hosts


def test_nothing_leaves_the_machine_but_the_update_check():
    unexpected = {host: files for host, files in _runtime_hosts().items() if host not in ALLOWED}
    assert unexpected == {}


def test_no_public_resolver_or_ip_literal():
    files = subprocess.run(["git", "ls-files", "--", *RUNTIME], cwd=REPO, capture_output=True, text=True, check=True)
    public = re.compile(r"\b(8\.8\.8\.8|8\.8\.4\.4|1\.1\.1\.1|1\.0\.0\.1|9\.9\.9\.9)\b")
    offenders = [n for n in files.stdout.split() if "/tests/" not in n and public.search(
        (REPO / n).read_text(encoding="utf-8", errors="ignore"))]
    assert offenders == []

