import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

SCRIPT = Path(__file__).with_name("winget-manifests.py")
spec = importlib.util.spec_from_file_location("winget_manifests", SCRIPT)
winget = importlib.util.module_from_spec(spec)
spec.loader.exec_module(winget)

SUMS = "a" * 64 + "  Bobine-Setup-9.9.9.exe\n" + "b" * 64 + " *Bobine-Setup-9.9.9-arm64.exe\n" + "c" * 64 + "  install.sh\n"


class WingetManifestTests(unittest.TestCase):
    def test_installers_use_release_digests(self):
        with tempfile.TemporaryDirectory() as tmp:
            sums = Path(tmp) / "SHA256SUMS"
            sums.write_text(SUMS, encoding="utf-8")
            files = winget.manifests(winget.read_sums(sums), "V9.9.9")
        installer = files["FantasmaGlad.Bobine.installer.yaml"]
        self.assertIn("InstallerType: inno", installer)
        self.assertIn("releases/download/V9.9.9/Bobine-Setup-9.9.9.exe\n    InstallerSha256: " + "A" * 64, installer)
        self.assertIn("Architecture: arm64\n    InstallerUrl: https://github.com/FantasmaGlad/Bobine/releases/download/V9.9.9/Bobine-Setup-9.9.9-arm64.exe\n    InstallerSha256: " + "B" * 64, installer)
        self.assertEqual(len(files), 4)
        for content in files.values():
            self.assertIn("\n\nPackageIdentifier: FantasmaGlad.Bobine\nPackageVersion: 9.9.9\n", content)
            self.assertIsInstance(yaml.safe_load(content), dict, "manifeste YAML invalide")

    def test_each_manifest_starts_with_its_schema_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            sums = Path(tmp) / "SHA256SUMS"
            sums.write_text(SUMS, encoding="utf-8")
            files = winget.manifests(winget.read_sums(sums), "V9.9.9")
        for name, kind in (("FantasmaGlad.Bobine.yaml", "version"), ("FantasmaGlad.Bobine.installer.yaml", "installer"),
                           ("FantasmaGlad.Bobine.locale.en-US.yaml", "defaultLocale"),
                           ("FantasmaGlad.Bobine.locale.fr-FR.yaml", "locale")):
            self.assertTrue(files[name].startswith(f"# yaml-language-server: $schema=https://aka.ms/winget-manifest.{kind}.1.12.0.schema.json\n"))

    def test_only_bobine_tags_are_accepted(self):
        with self.assertRaises(SystemExit):
            winget.manifests({"Bobine-Setup-5.1.1.exe": "A" * 64}, "assistant-V5.1.1")

    def test_missing_installer_and_rolling_tag_are_refused(self):
        with self.assertRaises(SystemExit):
            winget.manifests({"Bobine-Setup-9.9.9.exe": "A" * 64}, "V9.9.9")
        with tempfile.TemporaryDirectory() as tmp:
            sums = Path(tmp) / "SHA256SUMS"
            sums.write_text(SUMS, encoding="utf-8")
            result = subprocess.run([sys.executable, str(SCRIPT), str(sums), "canary", tmp], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
