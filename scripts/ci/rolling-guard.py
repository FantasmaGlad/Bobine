#!/usr/bin/env python3
"""Garde de monotonie des canaux glissants : refuse de publier un build plus ancien que celui déjà publié.

Sans elle, la relance d'un ancien run republie un ancien build et écrase le tag mobile, la release et les dépôts.

  rolling-guard.py --tag canary --sha <commit> --event push --attempt 1 [--require-tip origin/main]

Règles, dans l'ordre :
  1. avec --require-tip (Canary), le commit doit être la tête de la branche : sinon un run plus récent existe ou va exister ;
  2. le commit ne doit pas être un ancêtre strict de celui que porte déjà le tag mobile, sauf déclenchement manuel neuf
     (workflow_dispatch, première tentative) : revenir en arrière est alors un choix du mainteneur, signalé par un avertissement.
Écrit `publish=true|false` et `reason=` dans $GITHUB_OUTPUT ; sort avec 0 dans les deux cas, 2 si l'appel est invalide
(une référence introuvable est une erreur : jamais de publication à l'aveugle).
"""
import argparse
import os
import subprocess
import sys


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True)


def resolve(ref):
    result = git("rev-parse", "--verify", "--quiet", ref + "^{commit}")
    return result.stdout.strip() if result.returncode == 0 else None


def is_ancestor(older, newer):
    return git("merge-base", "--is-ancestor", older, newer).returncode == 0


def decide(sha, tip, published, event, attempt, ancestor):
    """Renvoie (publier, raison). `ancestor(a, b)` dit si a est un ancêtre de b."""
    if tip is not None and sha != tip:
        return False, f"{sha[:7]} n'est plus la tête de la branche ({tip[:7]}) : un run plus récent publie"
    if published is not None and sha != published and ancestor(sha, published):
        if event == "workflow_dispatch" and attempt == 1:
            return True, f"retour volontaire de {published[:7]} à {sha[:7]} (déclenchement manuel)"
        return False, f"{sha[:7]} est plus ancien que le build déjà publié ({published[:7]}) : relance d'un ancien run refusée"
    return True, "build plus récent ou égal au build publié"


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tag", required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--event", required=True)
    parser.add_argument("--attempt", type=int, default=1)
    parser.add_argument("--require-tip", metavar="REF")
    args = parser.parse_args(argv)

    sha = resolve(args.sha)
    if sha is None:
        print(f"::error::Commit {args.sha} introuvable.")
        return 2
    tip = None
    if args.require_tip:
        tip = resolve(args.require_tip)
        if tip is None:
            print(f"::error::Référence {args.require_tip} introuvable : pas de publication à l'aveugle.")
            return 2
    published = resolve("refs/tags/" + args.tag)  # absent à la toute première publication
    publish, reason = decide(sha, tip, published, args.event, args.attempt, is_ancestor)
    print(("::notice::" if publish else "::warning::") + f"Canal {args.tag} : {'publication' if publish else 'publication refusée'} ({reason}).")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
            output.write(f"publish={'true' if publish else 'false'}\nreason={reason}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
