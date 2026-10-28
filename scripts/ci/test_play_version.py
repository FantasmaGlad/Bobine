import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location("play_version", Path(__file__).with_name("resolve-play-version.py"))
resolver = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(resolver)


class PlayVersionTests(unittest.TestCase):
    def test_source_and_stable_tag_must_match(self):
        self.assertEqual(resolver.resolve("V5.0.6", "5.0.6\n"), "5.0.6")
        with self.assertRaises(ValueError):
            resolver.resolve("V5.0.6", "5.0.5")

    def test_only_strict_stable_tags_are_accepted(self):
        for tag in ("5.0.6", "V5.0.6-beta", "V5.0.6-canary", "V5.0.6-rc.1", "V5.0.6.1", "V5.0.6\n", 'V5.0.6";exit 0'):
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                resolver.resolve(tag, "5.0.6")
