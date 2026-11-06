"""Script de paquets de l'assistant : noms publiés stables par système, icônes du canal, un paquet par extension."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "assistant" / "scripts" / "bundle.py"
spec = importlib.util.spec_from_file_location("assistant_bundle", SCRIPT)
bundle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bundle)


class AssistantBundleTests(unittest.TestCase):
    def test_published_names(self):
        self.assertEqual(bundle.target_names("linux", "x64", "5.1.0"), {
            ".deb": "bobine-assistant_5.1.0_amd64.deb", ".rpm": "bobine-assistant-5.1.0.x86_64.rpm"})
        self.assertEqual(bundle.target_names("linux", "arm64", "canary"), {
            ".deb": "bobine-assistant_canary_arm64.deb", ".rpm": "bobine-assistant-canary.aarch64.rpm"})
        self.assertEqual(bundle.target_names("windows", "x64", "beta"), {".exe": "Bobine-Assistant-Setup-beta.exe"})
        self.assertEqual(bundle.target_names("macos", "arm64", "5.1.0"), {".dmg": "Bobine-Assistant-5.1.0-arm64.dmg"})

    def test_channel_icons_and_version(self):
        override = bundle.config_override("5.1.1+canary.7", "canary")
        self.assertEqual(override["version"], "5.1.1+canary.7")
        self.assertEqual(override["plugins"]["updater"]["endpoints"],
                         ["https://github.com/FantasmaGlad/Bobine/releases/download/assistant-canary/latest.json"])
        self.assertFalse(override["bundle"]["createUpdaterArtifacts"])
        self.assertTrue(bundle.config_override("5.1.1", "stable", True)["bundle"]["createUpdaterArtifacts"])
        self.assertTrue(all(path.startswith("icons/canary/") for path in override["bundle"]["icon"]))
        for path in override["bundle"]["icon"]:
            self.assertTrue((bundle.ASSISTANT / "src-tauri" / path).is_file(), path)

    def test_signature_binds_the_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            package = Path(tmp) / "bobine-assistant_5.1.1_amd64.deb"
            package.write_bytes(b"deb")
            commands = []
            original = bundle.subprocess.run

            def fake_run(command, check):
                commands.append(command)
                package.with_name(package.name + ".sig").write_text("signature")

            bundle.subprocess.run = fake_run
            try:
                bundle.sign([package], "/usr/bin/npx", "5.1.1")
            finally:
                bundle.subprocess.run = original
            self.assertIn("--app-version", commands[0])
            self.assertIn("5.1.1", commands[0])

    def test_exactly_one_package_per_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            produced, out = Path(tmp) / "bundle", Path(tmp) / "out"
            (produced / "deb").mkdir(parents=True)
            (produced / "deb" / "Bobine Assistant_5.1.0_amd64.deb").write_bytes(b"deb")
            written = bundle.collect(produced, {".deb": "bobine-assistant_5.1.0_amd64.deb"}, out)
            self.assertEqual([p.name for p in written], ["bobine-assistant_5.1.0_amd64.deb"])
            (produced / "deb" / "autre.deb").write_bytes(b"deb")
            with self.assertRaises(SystemExit):
                bundle.collect(produced, {".deb": "x.deb"}, out)
            with self.assertRaises(SystemExit):
                bundle.collect(produced, {".rpm": "x.rpm"}, out)


if __name__ == "__main__":
    unittest.main()
