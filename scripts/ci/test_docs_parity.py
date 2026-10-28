"""Keep the bilingual public documents aligned: same outline, valid anchors, no link to files that are never published."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
PAIRS = (
    ("docs/ARCHITECTURE.md", "docs/ARCHITECTURE.en.md"),
    ("docs/android-google-play.md", "docs/android-google-play.en.md"),
)


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def headings(text):
    """Markdown headings outside fenced code blocks, as (level, title)."""
    result, fenced = [], False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
        elif not fenced:
            match = re.match(r"^(#{1,6}) +(.*\S)\s*$", line)
            if match:
                result.append((len(match.group(1)), match.group(2)))
    return result


def anchors(text):
    """GitHub anchors of the headings, with the numeric suffix GitHub adds to repeated titles."""
    seen, found = {}, set()
    for _, title in headings(text):
        base = re.sub(r"[^\w\- ]", "", title.lower()).replace(" ", "-")
        count = seen.get(base, 0)
        seen[base] = count + 1
        found.add(base if count == 0 else f"{base}-{count}")
    return found


def section_number(title):
    match = re.match(r"^\d+(?:\.\d+)*", title)
    return match.group(0) if match else None


class BilingualDocumentTests(unittest.TestCase):
    def test_pairs_have_the_same_outline(self):
        for french, english in PAIRS:
            with self.subTest(pair=french):
                fr, en = headings(read(french)), headings(read(english))
                self.assertEqual([level for level, _ in fr], [level for level, _ in en], "heading levels differ")
                self.assertEqual([section_number(title) for _, title in fr], [section_number(title) for _, title in en],
                                 "section numbers differ")

    def test_internal_anchors_resolve(self):
        for path in (path for pair in PAIRS for path in pair):
            with self.subTest(document=path):
                text = read(path)
                links = re.findall(r"\]\(#([^)\s]+)\)", re.sub(r"```.*?```", "", text, flags=re.S))
                self.assertEqual([link for link in links if link not in anchors(text)], [])

    def test_no_link_to_files_that_stay_local(self):
        """Google Play bundles and Play APKs are built locally and never attached to a public release."""
        for path in sorted(ROOT.glob("docs/*.md")) + [ROOT / "README.md", ROOT / "README.fr.md"]:
            with self.subTest(document=path.name):
                found = re.findall(r"releases/download/[^)\s]*(?:\.aab|-play\.apk)", path.read_text(encoding="utf-8"))
                self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
