import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location("resolve_release", Path(__file__).with_name("resolve-release.py"))
resolver = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(resolver)


class ReleaseResolutionTests(unittest.TestCase):
    def resolve(self, event="workflow_dispatch", ref="refs/heads/main", **kwargs):
        return resolver.resolve("5.0.6", event, ref, **kwargs)

    def test_main_push_is_canary_with_fixed_filename(self):
        result = self.resolve(event="push", run="42")
        self.assertEqual((result["channel"], result["tag_name"], result["display_version"], result["deb_version"], result["filename_version"]),
                         ("canary", "canary", "5.0.6-canary", "5.0.6~0.canary.42", "canary"))

    def test_beta_requires_explicit_manual_input(self):
        result = self.resolve(beta=True, run="15")
        self.assertEqual((result["tag_name"], result["deb_version"], result["filename_version"]), ("beta", "5.0.6~1.beta.15", "beta"))
        self.assertEqual(self.resolve()["channel"], "none")

    def test_pull_request_has_no_publication(self):
        self.assertEqual(self.resolve(event="pull_request", ref="refs/pull/39/merge")["channel"], "none")

    def test_stable_tag_has_no_prerelease_suffix(self):
        for event, ref, values in [("push", "refs/tags/V5.0.6", {}), ("workflow_dispatch", "refs/heads/main", {"tag": "V5.0.6"})]:
            result = self.resolve(event, ref, **values)
            self.assertEqual((result["channel"], result["deb_version"], result["filename_version"]), ("stable", "5.0.6", "5.0.6"))

    def test_conflicting_intents_are_rejected(self):
        for values in ({"beta": True, "canary": True}, {"tag": "V5.0.6", "beta": True}, {"tag": "V5.0.6", "canary": True}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                self.resolve(**values)

    def test_invalid_tags_and_version_mismatch_are_rejected(self):
        for tag in ("V5.0.5", "V5.0.6-beta.1", "V5.0.6-rc.1", "canary", "V5.0.6\n", "V5.0.6;echo bad"):
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                self.resolve(tag=tag)

    def test_invalid_build_and_revision_are_rejected(self):
        for run in ("0", "-1", "1\n", "other"):
            with self.subTest(run=run), self.assertRaises(ValueError):
                self.resolve(canary=True, run=run)
        with self.assertRaises(ValueError):
            self.resolve(commit="a\nb")

    def test_manual_inputs_cannot_change_a_push_or_tag_intent(self):
        with self.assertRaises(ValueError):
            self.resolve(event="push", beta=True)
        with self.assertRaises(ValueError):
            self.resolve(ref="refs/tags/V5.0.6", beta=True)


if __name__ == "__main__":
    unittest.main()
