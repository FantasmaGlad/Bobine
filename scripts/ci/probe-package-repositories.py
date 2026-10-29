#!/usr/bin/env python3
"""Sonde de santé des dépôts de paquets publiés (packages.bobine.fit) : lecture seule, aucun secret.

  probe-package-repositories.py [--base-url URL] [--min-days 7] [--release canary=assets.json ...]

Pour chaque suite APT (stable, beta, canary) :
  - la clé publique servie porte l'empreinte attendue et InRelease est signé par elle ;
  - Valid-Until est éloigné d'au moins --min-days jours (absent : avertissement, apt ne l'expire alors jamais) ;
  - chaque paquet des index Packages répond à un HEAD ;
  - pour un canal glissant dont --release donne le JSON des assets GitHub (`gh api repos/<dépôt>/releases/tags/<canal>`),
    le SHA-256 du .deb du dépôt est celui de l'asset de la release (le dépôt suit la release).
Sort avec 1 au premier écart : l'échec du workflow planifié prévient le mainteneur par courriel GitHub.
"""
import argparse
import email.utils
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request

FINGERPRINT = os.environ.get("BOBINE_SIGNING_FINGERPRINT", "B77D96D72F84F36ACAA3F8729CBF497D829EE15A")
SUITES = ("stable", "beta", "canary")
ARCHITECTURES = ("amd64", "arm64")


def fields(text):
    return dict(re.findall(r"^([A-Za-z0-9-]+): (.*)$", text.split("\n\n")[0], re.M))


def packages(text):
    """Entrées d'un fichier Packages : liste de dictionnaires de champs."""
    return [dict(re.findall(r"^([A-Za-z0-9-]+): (.*)$", block, re.M)) for block in text.strip().split("\n\n") if block.strip()]


def check_release(suite, clear_text, now, min_days):
    """Contrôle les champs d'un Release lu après vérification de signature : (erreurs, avertissements)."""
    errors, warnings = [], []
    release = fields(clear_text)
    if release.get("Codename") != suite:
        errors.append(f"{suite} : Codename {release.get('Codename')!r} inattendu")
    expires = release.get("Valid-Until")
    if not expires:
        warnings.append(f"{suite} : pas de Valid-Until (la suite n'expire pas, mais n'est pas rafraîchie non plus)")
    else:
        margin = (email.utils.parsedate_to_datetime(expires).timestamp() - now) / 86400
        if margin < min_days:
            errors.append(f"{suite} : Valid-Until dans {margin:.1f} jours, {min_days:g} exigés")
    return errors, warnings


def check_follows_release(suite, entries, assets):
    """Le .deb de chaque architecture du dépôt a le SHA-256 de l'asset de la release du même canal."""
    errors = []
    digests = {asset["name"]: asset.get("digest", "") for asset in assets}
    for architecture in ARCHITECTURES:
        name = f"bobine_{suite}_{architecture}.deb"
        match = [entry for entry in entries if entry.get("Architecture") == architecture]
        if len(match) != 1:
            errors.append(f"{suite} : {len(match)} paquet(s) {architecture} dans l'index, un attendu")
        elif name not in digests:
            errors.append(f"{suite} : asset {name} absent de la release")
        elif digests[name] != "sha256:" + match[0].get("SHA256", ""):
            errors.append(f"{suite} : {architecture} diffère de la release (dépôt {match[0].get('SHA256', '')[:12]}, release {digests[name][7:19]})")
    return errors


def fetch(url, method="GET"):
    request = urllib.request.Request(url, method=method, headers={"User-Agent": "bobine-package-probe"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read() if method == "GET" else b""


def gpg_decrypt(home, path):
    return subprocess.run(["gpg", "--homedir", home, "--batch", "--decrypt", path], capture_output=True, text=True)


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default="https://packages.bobine.fit")
    parser.add_argument("--min-days", type=float, default=7)
    parser.add_argument("--release", action="append", default=[], metavar="CANAL=FICHIER.json")
    parser.add_argument("--retries", type=int, default=3, help="essais pour l'égalité avec la release (une publication peut être en cours)")
    parser.add_argument("--retry-delay", type=float, default=60)
    args = parser.parse_args(argv)
    base = args.base_url.rstrip("/")
    releases = {}
    for item in args.release:
        channel, _, path = item.partition("=")
        releases[channel] = json.load(open(path, encoding="utf-8")).get("assets", [])
    errors, warnings = [], []
    with tempfile.TemporaryDirectory() as home:
        os.chmod(home, 0o700)
        key = os.path.join(home, "bobine.gpg")
        open(key, "wb").write(fetch(f"{base}/bobine.gpg"))
        listing = subprocess.run(["gpg", "--homedir", home, "--batch", "--with-colons", "--import-options", "show-only", "--import", key], capture_output=True, text=True).stdout
        if f"fpr:::::::::{FINGERPRINT}:" not in listing:
            errors.append("bobine.gpg : empreinte inattendue")
        else:
            subprocess.run(["gpg", "--homedir", home, "--batch", "--import", key], capture_output=True, check=True)
            for suite in SUITES:
                path = os.path.join(home, f"InRelease-{suite}")
                open(path, "wb").write(fetch(f"{base}/debian/dists/{suite}/InRelease"))
                signed = gpg_decrypt(home, path)
                if signed.returncode != 0 or FINGERPRINT[-16:] not in signed.stderr.replace(" ", ""):
                    errors.append(f"{suite} : InRelease non signé par la clé attendue")
                    continue
                suite_errors, suite_warnings = check_release(suite, signed.stdout, time.time(), args.min_days)
                errors += suite_errors
                warnings += suite_warnings
                for architecture in ARCHITECTURES:
                    index = fetch(f"{base}/debian/dists/{suite}/main/binary-{architecture}/Packages").decode()
                    for entry in packages(index):
                        try:
                            fetch(f"{base}/debian/{entry['Filename']}", "HEAD")
                        except OSError as problem:
                            errors.append(f"{suite} : {entry['Filename']} injoignable ({problem})")
                if suite in releases:
                    entries = [entry for architecture in ARCHITECTURES
                               for entry in packages(fetch(f"{base}/debian/dists/{suite}/main/binary-{architecture}/Packages").decode())]
                    mismatch = check_follows_release(suite, entries, releases[suite])
                    for attempt in range(1, args.retries):
                        if not mismatch:
                            break
                        time.sleep(args.retry_delay)
                        entries = [entry for architecture in ARCHITECTURES
                                   for entry in packages(fetch(f"{base}/debian/dists/{suite}/main/binary-{architecture}/Packages").decode())]
                        mismatch = check_follows_release(suite, entries, releases[suite])
                    errors += mismatch
    for warning in warnings:
        print(f"::warning::{warning}")
    for error in errors:
        print(f"::error::{error}")
    print("Sonde : " + ("échec" if errors else "dépôts sains") + f" ({len(errors)} erreur(s), {len(warnings)} avertissement(s)).")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
