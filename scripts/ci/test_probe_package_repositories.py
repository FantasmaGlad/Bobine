"""The health probe flags a suite about to expire, a bad signature and a repository that lags behind its release."""
import functools
import hashlib
import http.server
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/ci/probe-package-repositories.py"
PREPARE = ROOT / "scripts/ci/prepare-package-repository.sh"
SPEC = importlib.util.spec_from_file_location("probe", SCRIPT)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)

NOW = 1_800_000_000
RELEASE = "Origin: Bobine\nCodename: beta\nDate: Sat, 24 Oct 2026 13:14:01 UTC\nValid-Until: {}\n"


def valid_until(days):
    return time.strftime("%a, %d %b %Y %H:%M:%S UTC", time.gmtime(NOW + days * 86400))


class ReleaseChecksTests(unittest.TestCase):
    def check(self, text, suite="beta", days=7):
        return probe.check_release(suite, text, NOW, days)

    def test_a_suite_with_margin_is_healthy(self):
        self.assertEqual(self.check(RELEASE.format(valid_until(300))), ([], []))

    def test_a_suite_close_to_expiry_is_an_error(self):
        errors, _ = self.check(RELEASE.format(valid_until(3)))
        self.assertEqual(len(errors), 1)
        self.assertIn("beta : Valid-Until dans 3.0 jours", errors[0])

    def test_an_expired_suite_is_an_error(self):
        self.assertTrue(self.check(RELEASE.format(valid_until(-1)))[0])

    def test_a_suite_without_valid_until_is_only_a_warning(self):
        errors, warnings = self.check("Codename: beta\nDate: x\n")
        self.assertEqual(errors, [])
        self.assertEqual(len(warnings), 1)

    def test_a_release_served_for_another_suite_is_an_error(self):
        self.assertTrue(self.check(RELEASE.format(valid_until(300)), suite="canary")[0])


class FollowsReleaseTests(unittest.TestCase):
    ENTRIES = [{"Architecture": "amd64", "SHA256": "aa" * 32}, {"Architecture": "arm64", "SHA256": "bb" * 32}]

    def assets(self, amd64="aa" * 32, arm64="bb" * 32):
        return [{"name": "bobine_canary_amd64.deb", "digest": "sha256:" + amd64}, {"name": "bobine_canary_arm64.deb", "digest": "sha256:" + arm64}]

    def test_identical_digests_pass(self):
        self.assertEqual(probe.check_follows_release("canary", self.ENTRIES, self.assets()), [])

    def test_a_repository_behind_its_release_fails(self):
        errors = probe.check_follows_release("canary", self.ENTRIES, self.assets(amd64="cc" * 32))
        self.assertEqual(len(errors), 1)
        self.assertIn("amd64 diffère de la release", errors[0])

    def test_a_missing_asset_or_package_fails(self):
        self.assertTrue(probe.check_follows_release("canary", self.ENTRIES, self.assets()[:1]))
        self.assertTrue(probe.check_follows_release("canary", self.ENTRIES[:1], self.assets()))


MISSING = [tool for tool in ("reprepro", "dpkg-deb", "gpg") if shutil.which(tool) is None]


@unittest.skipIf(MISSING, f"outils absents : {', '.join(MISSING)}")
class ProbeOnARealRepositoryTests(unittest.TestCase):
    """A repository built by prepare-package-repository.sh and served over HTTP, probed as in production."""

    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix="probe-")
        cls.addClassCleanup(cls.directory.cleanup)
        base = Path(cls.directory.name)
        home = base / "gnupg"
        home.mkdir(mode=0o700)
        cls.env = dict(os.environ, GNUPGHOME=str(home), LC_ALL="C")
        subprocess.run(["gpg", "--batch", "--passphrase", "", "--quick-generate-key", "Bobine Test <contact@bobine.fit>", "ed25519", "sign", "never"],
                       check=True, capture_output=True, env=cls.env)
        listing = subprocess.run(["gpg", "--batch", "--with-colons", "--list-secret-keys"], check=True, capture_output=True, text=True, env=cls.env).stdout
        cls.env["BOBINE_SIGNING_FINGERPRINT"] = re.search(r"^fpr:::::::::([A-F0-9]{40}):", listing, re.M).group(1)
        packages = base / "packages"
        packages.mkdir()
        cls.debs = {}
        for architecture in ("amd64", "arm64"):
            tree = base / f"tree-{architecture}"
            (tree / "DEBIAN").mkdir(parents=True)
            (tree / "DEBIAN/control").write_text(f"Package: bobine\nVersion: 1.0-1\nArchitecture: {architecture}\nSection: misc\nPriority: optional\nMaintainer: t <t@example.org>\nDescription: test\n")
            deb = packages / f"bobine_1.0-1_{architecture}.deb"
            subprocess.run(["dpkg-deb", "--build", str(tree), str(deb)], check=True, capture_output=True)
            cls.debs[architecture] = hashlib.sha256(deb.read_bytes()).hexdigest()
        cls.pages = base / "pages"
        cls.pages.mkdir()
        for channel in ("stable", "beta", "canary"):
            subprocess.run(["bash", str(PREPARE), "deb", channel, str(packages), str(cls.pages)], check=True, capture_output=True, env=cls.env)
        class Quiet(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *args):
                pass

        handler = functools.partial(Quiet, directory=str(cls.pages))
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.addClassCleanup(cls.server.shutdown)
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"

    def run_probe(self, amd64=None, **environment):
        release = Path(self.directory.name, "canary.json")
        release.write_text(json.dumps({"assets": [{"name": "bobine_canary_amd64.deb", "digest": "sha256:" + (amd64 or self.debs["amd64"])},
                                                  {"name": "bobine_canary_arm64.deb", "digest": "sha256:" + self.debs["arm64"]}]}))
        return subprocess.run(["python3", str(SCRIPT), "--base-url", self.url, "--release", f"canary={release}", "--retries", "1"],
                              capture_output=True, text=True, env=dict(self.env, **environment))

    def test_a_healthy_repository_passes(self):
        result = self.run_probe()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("dépôts sains", result.stdout)

    def test_a_repository_that_differs_from_its_release_fails(self):
        result = self.run_probe(amd64="0" * 64)
        self.assertEqual(result.returncode, 1)
        self.assertIn("canary : amd64 diffère de la release", result.stdout)

    def test_a_signature_from_another_key_fails(self):
        result = self.run_probe(BOBINE_SIGNING_FINGERPRINT="A" * 40)
        self.assertEqual(result.returncode, 1)
        self.assertIn("empreinte inattendue", result.stdout)

    def test_a_suite_about_to_expire_fails(self):
        result = subprocess.run(["python3", str(SCRIPT), "--base-url", self.url, "--min-days", "400"], capture_output=True, text=True, env=self.env)
        self.assertEqual(result.returncode, 1)
        self.assertIn("beta : Valid-Until dans", result.stdout)


if __name__ == "__main__":
    unittest.main()
