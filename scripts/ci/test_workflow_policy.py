"""Garde-fous des workflows GitHub, lus comme du texte (aucune dépendance YAML) :
déclencheur de tag aligné sur resolve-release.py, republication manuelle d'un tag
construite depuis ce tag."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLAY = (ROOT / ".github/workflows/play-aab.yml").read_text(encoding="utf-8")
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
            if "path: .workflow-tools" in block:
                continue  # révision du workflow, pour ses actions locales (publication d'un ancien tag Stable)
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


class PlayBundlesTests(unittest.TestCase):
    def test_les_bundles_play_ne_sont_jamais_publies_sur_la_release(self):
        for interdit in ("attach_to_release", "gh release", "contents: write"):
            self.assertNotIn(interdit, PLAY)
        self.assertRegex(PLAY, r"(?m)^permissions:\n  contents: read\n")
        self.assertRegex(PLAY, r"(?m)^    timeout-minutes: \d+$")


class ToolchainRustTests(unittest.TestCase):
    JOBS_RUST = (
        "devices-sidecar", "media-component", "android-build",
        "windows-build", "windows-build-arm64", "macos-build",
    )

    def test_chaque_job_qui_appelle_cargo_installe_la_toolchain_avant(self):
        parts = jobs(CI)
        self.assertIn("rustup toolchain install", parts["linux-deb"])  # cargo y est lancé par les scripts de paquet
        for name in self.JOBS_RUST:
            body = parts[name]
            install = body.find("rustup toolchain install")
            self.assertGreaterEqual(install, 0, f"job {name} sans rustup toolchain install")
            appel = re.search(r"(?m)^[^#\n]*(\bcargo (build|clippy|test|fmt)\b|build-media-android\.sh)", body)
            self.assertIsNotNone(appel, f"job {name} sans appel à cargo : liste obsolète")
            self.assertLess(install, appel.start(), f"job {name} : cargo avant l'installation de la toolchain")


class DocumentationSeuleTests(unittest.TestCase):
    """Documentation seule : rien n'est construit ni publié. Pull request : seuls les jobs de la zone touchée."""

    # Portée dont dépend chaque job : `code` tourne à toute modification de code, les autres seulement quand
    # une pull request touche leur zone (un push sur main, un tag ou un déclenchement manuel construisent tout).
    PORTEES = {
        "frontend": "code", "firefox-smoke": "code", "backend": "code", "backend-android-compat": "code",
        "install-script": "code", "devices-sidecar": "devices", "media-component": "media",
        "android-build": "android", "android-startup": "android", "windows-build": "packaging",
        "windows-build-arm64": "packaging", "linux-deb": "packaging", "macos-build": "packaging",
    }

    def test_chaque_job_de_construction_depend_de_la_portee(self):
        parts = jobs(CI)
        for name, portee in self.PORTEES.items():
            self.assertIn(f"    if: needs.version.outputs.{portee} == 'true'", parts[name], name)

    def test_une_pull_request_ne_construit_aucun_paquet_sans_raison(self):
        version = jobs(CI)["version"]
        self.assertIn('if [ "$GITHUB_EVENT_NAME" != pull_request ]; then\n            portee true; exit 0', version)
        for cle in ("packaging", "android", "media", "devices"):
            self.assertIn(f'echo "{cle}=$(touche ', version)

    def test_chaque_artefact_a_une_retention_courte(self):
        for texte in (CI, PLAY):
            envois = re.findall(r"uses: actions/upload-artifact@[^\n]*\n(?:[^\n]*\n){0,2}? +with:\n +retention-days: ", texte)
            self.assertEqual(len(envois), texte.count("actions/upload-artifact@"))

    def test_tag_et_declenchement_manuel_construisent_tout(self):
        version = jobs(CI)["version"]
        self.assertIn('[ "$GITHUB_EVENT_NAME" = workflow_dispatch ] || [[ "$GITHUB_REF" == refs/tags/* ]]', version)

    def test_ci_ok_n_accepte_un_job_ignore_que_hors_de_sa_portee(self):
        ci_ok = jobs(CI)["ci-ok"]
        self.assertIn('{ [ "$3" = false ] && [ "$2" = skipped ]; }', ci_ok)
        for name, portee in self.PORTEES.items():
            self.assertIn(f'controle {name} "${{{{ needs.{name}.result }}}}" "${portee.upper()}"', ci_ok)


if __name__ == "__main__":
    unittest.main()
