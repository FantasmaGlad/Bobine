import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location("signing", Path(__file__).with_name("check-android-signing.py"))
signing = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(signing)


class AndroidSigningTests(unittest.TestCase):
    def test_four_secrets_are_required_for_publication(self):
        self.assertTrue(signing.configured(dict.fromkeys(signing.NAMES, "provided")))
        for absent in signing.NAMES:
            with self.subTest(absent=absent), self.assertRaises(ValueError):
                signing.configured({name: "provided" for name in signing.NAMES if name != absent})

    def test_pr_without_any_secret_is_explicitly_unsigned(self):
        self.assertFalse(signing.configured({}, allow_missing=True))
        with self.assertRaises(ValueError):
            signing.configured({})

    def test_pr_partial_secrets_are_an_error(self):
        with self.assertRaises(ValueError):
            signing.configured({signing.NAMES[0]: "provided"}, allow_missing=True)


if __name__ == "__main__":
    unittest.main()
