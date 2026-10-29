#!/usr/bin/env python3
"""Durée de validité (ValidFor) des suites du dépôt APT et contrôle de la marge restante.

  apt-validity.py apply <conf/distributions>       impose la durée de chaque suite
  apt-validity.py check <dossier debian> [jours]   vérifie signature et marge de Valid-Until (14 jours par défaut)

La Stable et la Beta durent un an : la Beta n'est publiée qu'à la main et un fichier Release expiré fait échouer
`apt update` (« Release file is expired »). La Canary dure 30 jours, car chaque push sur main la republie. Le
workflow planifié de rafraîchissement ré-exporte et re-signe les trois suites chaque semaine, sans changer les paquets.
"""
import email.utils
import pathlib
import subprocess
import sys
import time

DEFAULT_VALIDITY = "365d"
VALIDITY = {"canary": "30d"}
DEFAULT_MIN_DAYS = 14


def apply_policy(text):
    """Renvoie le contenu du fichier conf/distributions avec la durée de chaque suite imposée."""
    blocks = []
    for block in text.strip().split("\n\n"):
        lines = [line for line in block.splitlines() if not line.startswith("ValidFor:")]
        codename = next((line.split(":", 1)[1].strip() for line in lines if line.startswith("Codename:")), "")
        lines.append("ValidFor: " + VALIDITY.get(codename, DEFAULT_VALIDITY))
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + "\n"


def apply(path):
    config = pathlib.Path(path)
    config.write_text(apply_policy(config.read_text()))


def valid_until(clear_text):
    for line in clear_text.splitlines():
        if line.startswith("Valid-Until:"):
            return email.utils.parsedate_to_datetime(line.split(":", 1)[1].strip()).timestamp()
    return None


def check(debian_dir, min_days=DEFAULT_MIN_DAYS):
    """Chaque suite doit porter une signature valide et un Valid-Until éloigné d'au moins min_days jours."""
    problems = []
    for release in sorted(pathlib.Path(debian_dir, "dists").glob("*/InRelease")):
        suite = release.parent.name
        signed = subprocess.run(["gpg", "--batch", "--decrypt", str(release)], capture_output=True, text=True)
        if signed.returncode != 0:
            problems.append(f"{suite} : signature invalide")
            continue
        expires = valid_until(signed.stdout)
        if expires is None:
            problems.append(f"{suite} : pas de Valid-Until")
            continue
        margin = (expires - time.time()) / 86400
        print(f"{suite} : Valid-Until dans {margin:.1f} jours")
        if margin < min_days:
            problems.append(f"{suite} : {margin:.1f} jours de marge, {min_days} exigés")
    if not problems and not list(pathlib.Path(debian_dir, "dists").glob("*/InRelease")):
        problems.append("aucune suite trouvée")
    return problems


def main(argv):
    if len(argv) >= 3 and argv[1] == "apply":
        apply(argv[2])
        return 0
    if len(argv) >= 3 and argv[1] == "check":
        problems = check(argv[2], float(argv[3]) if len(argv) > 3 else DEFAULT_MIN_DAYS)
        for problem in problems:
            print(problem, file=sys.stderr)
        return 1 if problems else 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
