from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]


class PublicDocumentTests(unittest.TestCase):
    def test_no_link_to_files_that_stay_local(self):
        for path in sorted(ROOT.glob("docs/**/*.md")) + [ROOT / "README.md", ROOT / "README.fr.md"]:
            with self.subTest(document=path.name):
                found = re.findall(r"releases/download/[^)\s]*(?:\.aab|-play\.apk)", path.read_text(encoding="utf-8"))
                self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
