"""The APT repository is published for any channel and refreshed without touching a package (needs reprepro, dpkg-deb, gpg)."""
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
PREPARE = ROOT / "scripts/ci/prepare-package-repository.sh"
REFRESH = ROOT / "scripts/ci/refresh-apt-release.sh"
MISSING = [tool for tool in ("reprepro", "dpkg-deb", "gpg") if shutil.which(tool) is None]


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@unittest.skipIf(MISSING, f"outils absents : {', '.join(MISSING)}")
class AptRepositoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix="apt-")
        cls.addClassCleanup(cls.directory.cleanup)
        base = Path(cls.directory.name)
        cls.home = base / "gnupg"
        cls.home.mkdir(mode=0o700)
        cls.env = dict(os.environ, GNUPGHOME=str(cls.home), LC_ALL="C")
        subprocess.run(["gpg", "--batch", "--passphrase", "", "--quick-generate-key", "Bobine Test <contact@bobine.fit>", "ed25519", "sign", "never"],
                       check=True, capture_output=True, env=cls.env)
        listing = subprocess.run(["gpg", "--batch", "--with-colons", "--list-secret-keys"], check=True, capture_output=True, text=True, env=cls.env).stdout
        cls.env["BOBINE_SIGNING_FINGERPRINT"] = re.search(r"^fpr:::::::::([A-F0-9]{40}):", listing, re.M).group(1)
        cls.packages = base / "packages"
        cls.packages.mkdir()
        for architecture in ("amd64", "arm64"):
            tree = base / f"tree-{architecture}"
            (tree / "DEBIAN").mkdir(parents=True)
            (tree / "DEBIAN/control").write_text(f"Package: bobine\nVersion: 1.0-1\nArchitecture: {architecture}\nSection: misc\nPriority: optional\nMaintainer: t <t@example.org>\nDescription: test\n")
            subprocess.run(["dpkg-deb", "--build", str(tree), str(cls.packages / f"bobine_1.0-1_{architecture}.deb")], check=True, capture_output=True)

    def setUp(self):
        self.pages = Path(self.directory.name, f"pages-{self.id().rsplit('.', 1)[-1]}")
        self.pages.mkdir()
        self.debian = self.pages / "debian"

    def run_script(self, script, *arguments):
        return subprocess.run(["bash", str(script), *arguments], capture_output=True, text=True, env=self.env)

    def prepare(self, channel):
        result = self.run_script(PREPARE, "deb", channel, str(self.packages), str(self.pages))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def release(self, suite):
        return subprocess.run(["gpg", "--batch", "--decrypt", str(self.debian / "dists" / suite / "InRelease")], capture_output=True, text=True, env=self.env, check=True).stdout

    def fields(self, suite):
        return dict(re.findall(r"^([A-Za-z-]+): (.*)$", self.release(suite), re.M))

    def untouched_files(self):
        return {str(path.relative_to(self.debian)): sha256(path) for path in sorted(self.debian.rglob("*"))
                if path.is_file() and (path.parts[-len(path.relative_to(self.debian).parts)] == "pool" or path.name in ("Packages", "Packages.gz"))}

    def test_every_channel_is_published_with_its_validity(self):
        for channel in ("stable", "beta", "canary"):
            self.prepare(channel)
        for channel, days in (("stable", 365), ("beta", 365), ("canary", 30)):
            expires = time.mktime(time.strptime(self.fields(channel)["Valid-Until"], "%a, %d %b %Y %H:%M:%S %Z")) - time.timezone
            self.assertAlmostEqual((expires - time.time()) / 86400, days, delta=1, msg=channel)

    def test_unknown_channel_is_refused(self):
        result = self.run_script(PREPARE, "deb", "nightly", str(self.packages), str(self.pages))
        self.assertEqual(result.returncode, 2)

    def test_refresh_extends_expiring_and_unlimited_suites_without_touching_packages(self):
        for channel in ("stable", "beta", "canary"):
            self.prepare(channel)
        # Etat constaté en production : suites stable et beta publiées avant l'ajout de Valid-Until, canary proche de son expiration.
        conf = self.debian / "conf/distributions"
        blocks = []
        for block in conf.read_text().strip().split("\n\n"):
            lines = [line for line in block.splitlines() if not line.startswith("ValidFor:")]
            if "Codename: canary" in lines:
                lines.append("ValidFor: 1d")
            blocks.append("\n".join(lines))
        conf.write_text("\n\n".join(blocks) + "\n")
        subprocess.run(["reprepro", "-b", str(self.debian), "export"], check=True, capture_output=True, env=self.env)
        self.assertNotIn("Valid-Until", self.fields("stable"))
        self.assertNotIn("Valid-Until", self.fields("beta"))
        stale = subprocess.run(["python3", str(ROOT / "scripts/ci/apt-validity.py"), "check", str(self.debian)], capture_output=True, text=True, env=self.env)
        self.assertEqual(stale.returncode, 1)
        self.assertIn("beta : pas de Valid-Until", stale.stderr)
        self.assertIn("canary : ", stale.stderr)

        before_files, before_date = self.untouched_files(), self.fields("beta")["Date"]
        self.assertTrue(before_files)
        time.sleep(1.1)
        result = self.run_script(REFRESH, str(self.pages))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        self.assertEqual(self.untouched_files(), before_files)
        self.assertNotEqual(self.fields("beta")["Date"], before_date)
        for suite in ("stable", "beta", "canary"):
            self.assertIn("Valid-Until", self.fields(suite), suite)
        durations = dict(re.findall(r"^Codename: (\w+)\n(?:.*\n)*?ValidFor: (\w+)$", conf.read_text(), re.M))
        self.assertEqual(durations, {"stable": "365d", "beta": "365d", "canary": "30d"})
        self.assertEqual(subprocess.run(["gpg", "--batch", "--verify", str(self.debian / "dists/beta/Release.gpg"), str(self.debian / "dists/beta/Release")],
                                        capture_output=True, env=self.env).returncode, 0)

    def test_refresh_refuses_a_folder_without_repository(self):
        self.assertEqual(self.run_script(REFRESH, str(self.pages)).returncode, 2)


if __name__ == "__main__":
    unittest.main()
