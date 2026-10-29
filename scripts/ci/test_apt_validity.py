"""APT suite validity: one year for Stable and Beta (the Beta is only published by hand), 30 days for the rebuilt Canary."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("apt_validity", Path(__file__).with_name("apt-validity.py"))
validity = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validity)

CONF = """Origin: Bobine
Suite: stable
Codename: stable
Architectures: amd64 arm64
SignWith: contact@bobine.fit
ValidFor: 365d

Origin: Bobine
Suite: canary
Codename: canary
Architectures: amd64 arm64
SignWith: contact@bobine.fit
ValidFor: 30d

Origin: Bobine
Suite: beta
Codename: beta
Architectures: amd64 arm64
SignWith: contact@bobine.fit
ValidFor: 30d
"""


def durations(text):
    result = {}
    for block in text.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines())
        result[fields["Codename"]] = fields.get("ValidFor")
    return result


class PolicyTests(unittest.TestCase):
    def test_beta_lasts_a_year_like_stable_and_canary_30_days(self):
        self.assertEqual(durations(validity.apply_policy(CONF)), {"stable": "365d", "canary": "30d", "beta": "365d"})

    def test_a_suite_without_any_duration_receives_one(self):
        bare = "Codename: beta\nArchitectures: amd64\n\nCodename: canary\nArchitectures: amd64\n"
        self.assertEqual(durations(validity.apply_policy(bare)), {"beta": "365d", "canary": "30d"})

    def test_a_suite_name_is_not_confused_with_its_codename(self):
        self.assertEqual(durations(validity.apply_policy("Codename: beta\nSuite: canary\n"))["beta"], "365d")

    def test_applying_twice_changes_nothing(self):
        once = validity.apply_policy(CONF)
        self.assertEqual(validity.apply_policy(once), once)

    def test_other_fields_are_kept_in_order(self):
        result = validity.apply_policy(CONF)
        self.assertIn("SignWith: contact@bobine.fit\nValidFor: 365d", result)
        self.assertTrue(result.endswith("\n") and not result.endswith("\n\n"))

    def test_apply_rewrites_the_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "distributions")
            path.write_text(CONF)
            validity.apply(path)
            self.assertEqual(durations(path.read_text())["beta"], "365d")

    def test_valid_until_is_read_from_a_release_text(self):
        text = "Codename: beta\nValid-Until: Fri, 27 Nov 2026 13:47:11 UTC\n"
        self.assertEqual(validity.valid_until(text), 1795787231.0)
        self.assertIsNone(validity.valid_until("Codename: beta\n"))


if __name__ == "__main__":
    unittest.main()
