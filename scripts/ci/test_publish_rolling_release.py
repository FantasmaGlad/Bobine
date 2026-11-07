"""A rolling release is updated in place: never deleted, so no 404 window and no empty channel after a failed upload."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).with_name("publish-rolling-release.sh")

FAKE_GH = r"""#!/usr/bin/env bash
# Fake gh: records every call; `release view` answers from $FAKE_GH_ASSETS (one name per line) or fails with $FAKE_GH_VIEW_ERROR.
echo "$*" >> "$FAKE_GH_LOG"
if [ "$1 $2" = "release view" ]; then
    if [ -n "${FAKE_GH_VIEW_ERROR:-}" ]; then echo "$FAKE_GH_VIEW_ERROR" >&2; exit 1; fi
    cat "$FAKE_GH_ASSETS"
fi
exit 0
"""


class PublishRollingReleaseTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        self.bin = root / "bin"
        self.bin.mkdir()
        (self.bin / "gh").write_text(FAKE_GH)
        (self.bin / "gh").chmod(0o755)
        self.assets = root / "release-assets"
        self.assets.mkdir()
        for name in ("Bobine-canary.apk", "bobine_canary_amd64.deb", "SHA256SUMS", "SHA256SUMS.asc"):
            (self.assets / name).write_text(name)
        self.notes = root / "notes.md"
        self.notes.write_text("notes")
        self.log = root / "gh.log"
        self.published = root / "published.txt"
        self.published.write_text("")

    def run_script(self, existing=None, view_error=None):
        if existing is not None:
            self.published.write_text("\n".join(existing) + "\n")
        environment = dict(os.environ, PATH=f"{self.bin}:{os.environ['PATH']}", FAKE_GH_LOG=str(self.log), FAKE_GH_ASSETS=str(self.published))
        if view_error:
            environment["FAKE_GH_VIEW_ERROR"] = view_error
        result = subprocess.run(["bash", str(SCRIPT), "canary", str(self.assets), "Titre", str(self.notes), "abc123"],
                                capture_output=True, text=True, env=environment)
        calls = self.log.read_text().splitlines() if self.log.exists() else []
        return result, calls

    def test_an_existing_release_is_updated_and_never_deleted(self):
        result, calls = self.run_script(existing=["Bobine-canary.apk", "bobine_canary_amd64.deb", "SHA256SUMS", "SHA256SUMS.asc"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse([call for call in calls if call.startswith("release delete ")], calls)
        self.assertFalse([call for call in calls if call.startswith("release create")], calls)
        uploads = [call for call in calls if call.startswith("release upload")]
        self.assertEqual(len(uploads), 2)
        self.assertTrue(all(call.endswith("--clobber") for call in uploads))
        self.assertIn("SHA256SUMS", uploads[1])
        self.assertNotIn("SHA256SUMS", uploads[0])
        self.assertTrue(calls[-1].startswith("release edit canary --title Titre --notes-file"))

    def test_assets_that_left_the_lot_are_removed(self):
        result, calls = self.run_script(existing=["Bobine-canary.apk", "old-asset.rpm"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("release delete-asset canary old-asset.rpm --yes", calls)
        self.assertFalse([call for call in calls if call.startswith("release delete-asset") and "Bobine-canary.apk" in call])

    def test_a_missing_release_is_created_with_the_target_commit(self):
        result, calls = self.run_script(view_error="release not found")
        self.assertEqual(result.returncode, 0, result.stderr)
        creates = [call for call in calls if call.startswith("release create canary")]
        self.assertEqual(len(creates), 1)
        self.assertIn("--target abc123", creates[0])
        self.assertIn("--prerelease", creates[0])
        self.assertFalse([call for call in calls if call.startswith(("release upload", "release delete"))])

    def test_another_error_stops_the_publication_instead_of_creating_a_release(self):
        result, calls = self.run_script(view_error="HTTP 502: Bad Gateway")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse([call for call in calls if call.startswith(("release create", "release upload", "release delete"))])

    def test_empty_assets_directory_is_refused(self):
        for asset in self.assets.iterdir():
            asset.unlink()
        result, calls = self.run_script(existing=["x"])
        self.assertEqual(result.returncode, 2)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
