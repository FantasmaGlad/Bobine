import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ANDROID = ROOT / "android" / "app" / "src"
EMPTY_CATCH = re.compile(r"catch\s*\([^)]*\)\s*\{\s*\}")


def empty_kotlin_catches():
    found = []
    for path in sorted(ANDROID.rglob("*.kt")):
        text = path.read_text(encoding="utf-8")
        for match in EMPTY_CATCH.finditer(text):
            found.append(f"{path.relative_to(ROOT)}:{text.count(chr(10), 0, match.start()) + 1}")
    return found


def silent_python_handlers():
    found = []
    for path in sorted(ANDROID.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ExceptHandler) and all(isinstance(s, ast.Pass) for s in node.body):
                found.append(f"{path.relative_to(ROOT)}:{node.lineno}")
    return found


class AndroidErrorLoggingTest(unittest.TestCase):
    def test_no_empty_kotlin_catch(self):
        self.assertEqual(empty_kotlin_catches(), [])

    def test_no_silent_python_handler(self):
        self.assertEqual(silent_python_handlers(), [])


if __name__ == "__main__":
    unittest.main()
