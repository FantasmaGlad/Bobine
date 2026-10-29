"""Keep the rolling release notes complete: every required asset is offered and none is invented."""
import importlib.util
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("render_rolling_notes", Path(__file__).with_name("render-rolling-notes.py"))
renderer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(renderer)

MANIFESTS = {"SHA256SUMS", "SHA256SUMS.asc"}


def required_assets(channel):
    """Names that scripts/ci/verify-release-assets.sh requires for a rolling channel (version and package version are the channel)."""
    script = (ROOT / "scripts/ci/verify-release-assets.sh").read_text(encoding="utf-8")
    block = re.search(r"expected=\((.*?)\n\)", script, re.S).group(1)
    return {name.replace("${S}", channel).replace("${package_version}", channel) for name in re.findall(r'"([^"]+)"', block)}


def linked_assets(notes, channel):
    return set(re.findall(rf"releases/download/{channel}/([^)\s]+)", notes))


class RollingNotesTests(unittest.TestCase):
    channels = renderer.registry.ROLLING_CHANNEL_IDS

    def test_rolling_channels_are_the_ones_the_notes_know(self):
        self.assertEqual(set(self.channels), set(renderer.LABELS))

    def test_every_required_asset_is_linked_and_nothing_else(self):
        for channel in self.channels:
            with self.subTest(channel=channel):
                self.assertEqual(linked_assets(renderer.render(channel), channel), required_assets(channel))

    def test_without_manifests_drops_only_the_manifests(self):
        for channel in self.channels:
            with self.subTest(channel=channel):
                notes = renderer.render(channel, manifests=False)
                self.assertEqual(linked_assets(notes, channel), required_assets(channel) - MANIFESTS)
                self.assertNotIn("gpg --verify", notes)

    def test_each_family_has_its_repository_method_for_the_channel(self):
        for channel in self.channels:
            with self.subTest(channel=channel):
                notes = renderer.render(channel)
                for expected in (f"https://packages.bobine.fit/debian/ {channel} main",
                                 f"https://packages.bobine.fit/fedora/bobine-{channel}.repo",
                                 f"https://packages.bobine.fit/arch/{channel}/$arch",
                                 f"pacman-key --lsign-key {renderer.SIGNING_FINGERPRINT}",
                                 f"sudo ./install.sh --channel={channel}"):
                    self.assertIn(expected, notes)
                self.assertNotIn("@", re.sub(r"[\w.+-]+@[\w.-]+", "", notes), "unreplaced placeholder")

    def test_notes_state_the_glibc_floor_and_promise_nothing_untested(self):
        for channel in self.channels:
            with self.subTest(channel=channel):
                notes = renderer.render(channel)
                self.assertIn(f"glibc {renderer.glibc_floor()} ou plus récente", notes)
                self.assertIn("--add-repo", notes, "DNF 4 needs its own command")
                for promised in ("Debian 13 et 12", "24.04 et 22.04", "openSUSE", "Zypper"):
                    self.assertNotIn(promised, notes)

    def test_tables_are_well_formed(self):
        for channel in self.channels:
            with self.subTest(channel=channel):
                block = []
                for line in renderer.render(channel).splitlines() + [""]:
                    if line.startswith("|"):
                        block.append(len(re.sub(r"`[^`]*`", "", line).split("|")))
                    elif block:
                        self.assertEqual(len(set(block)), 1, f"inconsistent columns: {block}")
                        block = []

    def test_only_rolling_channels_are_rendered(self):
        for channel in ("stable", "alpha"):
            with self.assertRaises(ValueError):
                renderer.render(channel)


if __name__ == "__main__":
    unittest.main()
