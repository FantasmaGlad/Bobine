"""Garde-fous des workflows GitHub, lus comme du texte (aucune dépendance YAML) :
déclencheur de tag aligné sur resolve-release.py, republication manuelle d'un tag
construite depuis ce tag."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CI = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
RESOLVE = (ROOT / "scripts/ci/resolve-release.py").read_text(encoding="utf-8")


class TagTriggerTests(unittest.TestCase):
    def test_ci_n_ecoute_que_les_tags_que_resolve_release_accepte(self):
        stable = re.search(r're\.fullmatch\(r"(V\\d\+\\\.\\d\+\\\.\\d\+)", stable_tag\)', RESOLVE)
        self.assertIsNotNone(stable, "motif des tags Stable introuvable dans resolve-release.py")
        self.assertTrue(stable.group(1).startswith("V"))
        match = re.search(r"^    tags: \[(.*)\]$", CI, flags=re.M)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1).replace('"', "'"), "'V*'")


class TagCheckoutTests(unittest.TestCase):
    def test_chaque_checkout_du_depot_construit_le_tag_demande(self):
        steps = re.findall(r"^      - uses: actions/checkout@[^\n]*\n((?:        [^\n]*\n|          [^\n]*\n)*)", CI, flags=re.M)
        self.assertGreater(len(steps), 20)
        for block in steps:
            if "repository:" in block:
                continue  # dépôts tiers (gh-pages, BobineWeb) : pas ce dépôt
            self.assertIn("ref: ${{ inputs.tag }}", block, block)


# Jobs courts et sans compilation : le délai par défaut de GitHub (6 h) y reste toléré.
SANS_DELAI = {
    "version", "frontend", "backend-android-compat", "install-script", "ci-ok",
    "linux-package-signing", "notify-web-release",
}


def jobs(text: str) -> dict[str, str]:
    body = text.split("\njobs:\n", 1)[1]
    parts = re.split(r"^  ([a-z0-9-]+):$", body, flags=re.M)
    return dict(zip(parts[1::2], parts[2::2]))


class DroitsEtDelaisTests(unittest.TestCase):
    def test_droits_du_jeton_reduits_au_niveau_du_workflow(self):
        self.assertRegex(CI, r"(?m)^permissions:\n  contents: read\n")

    def test_chaque_job_lourd_a_un_delai_maximal(self):
        for name, body in jobs(CI).items():
            if name not in SANS_DELAI:
                self.assertRegex(body, r"(?m)^    timeout-minutes: \d+$", f"job {name} sans timeout-minutes")


if __name__ == "__main__":
    unittest.main()
