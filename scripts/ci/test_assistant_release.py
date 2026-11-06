"""Release de l'assistant à part de celle de Bobine : notes liant exactement les paquets exigés, et aucune release de Bobine
ne contient un installeur de l'assistant (la mise à jour intégrée y prend le premier .exe, .deb ou .dmg)."""
import importlib.util
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location("assistant_notes", HERE / "render-assistant-notes.py")
notes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(notes)
spec = importlib.util.spec_from_file_location("assistant_latest", HERE / "render-assistant-latest.py")
latest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(latest)


def required(suffix):
    script = (HERE / "verify-assistant-assets.sh").read_text(encoding="utf-8")
    block = re.search(r"expected=\((.*?)\n\)", script, re.S).group(1)
    return {name.replace("${S}", suffix) for name in re.findall(r'"([^"]+)"', block)} - {"SHA256SUMS", "SHA256SUMS.asc"}


class AssistantReleaseTests(unittest.TestCase):
    def test_notes_link_every_package_of_the_channel_release(self):
        for channel, tag, suffix in (("stable", "V5.1.1", "5.1.1"), ("beta", "beta", "beta"), ("canary", "canary", "canary")):
            with self.subTest(channel=channel):
                text = notes.render(channel, tag, suffix)
                linked = set(re.findall(rf"releases/download/assistant-{tag}/([^)\s]+)", text))
                # Les signatures, l'archive de mise à jour macOS et latest.json ne servent qu'à la mise à jour automatique.
                downloads = {n for n in required(suffix) if not n.endswith((".sig", ".app.tar.gz", "latest.json"))}
                self.assertEqual(linked, downloads)

    def test_bobine_release_refuses_assistant_installers(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            script = (HERE / "verify-release-assets.sh").read_text(encoding="utf-8")
            block = re.search(r"expected=\((.*?)\n\)", script, re.S).group(1)
            for name in re.findall(r'"([^"]+)"', block):
                (directory / name.replace("${S}", "canary").replace("${package_version}", "canary")).write_text("x")
            (directory / "Bobine-Assistant-Setup-canary.exe").write_text("x")
            result = subprocess.run(["bash", str(HERE / "verify-release-assets.sh"), str(directory), "canary"],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("assistant", result.stdout + result.stderr)


    def test_latest_json_lists_each_installable_package_with_its_signature(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            for name in required("canary"):
                (directory / name).write_text(f"signature de {name}" if name.endswith(".sig") else "x")
            data = latest.manifest(directory, "assistant-canary", "5.1.1+canary.412")
            self.assertEqual(data["version"], "5.1.1+canary.412")
            self.assertEqual(set(data["platforms"]), {"windows-x86_64", "darwin-aarch64", "linux-x86_64-deb", "linux-x86_64-rpm"})
            deb = data["platforms"]["linux-x86_64-deb"]
            self.assertEqual(deb["url"], "https://github.com/FantasmaGlad/Bobine/releases/download/assistant-canary/bobine-assistant_canary_amd64.deb")
            self.assertEqual(deb["signature"], "signature de bobine-assistant_canary_amd64.deb.sig")
            (directory / "Bobine-Assistant-canary-arm64.app.tar.gz.sig").unlink()
            with self.assertRaises(SystemExit):
                latest.manifest(directory, "assistant-canary", "5.1.1+canary.412")


if __name__ == "__main__":
    unittest.main()
