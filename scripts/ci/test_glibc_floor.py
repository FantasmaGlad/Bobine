"""The glibc floor of the deb and rpm packages is announced once and checked against the binaries they ship."""
import importlib.util
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "packaging/common/glibc_floor.sh"
DECLARED = (ROOT / "packaging/common/MIN_GLIBC").read_text(encoding="utf-8").strip()
NOTES_SCRIPT = ROOT / "scripts/ci/render-rolling-notes.py"


def run(function, *arguments, floor_file=None):
    environment = dict(os.environ)
    if floor_file:
        environment["BOBINE_MIN_GLIBC_FILE"] = str(floor_file)
    return subprocess.run(["bash", "-c", 'set -euo pipefail; source "$1"; shift; "$@"', "_", str(HELPER), function, *arguments],
                          capture_output=True, text=True, env=environment)


class Tree:
    """Temporary directory of fake binaries: relative name -> (content, executable)."""

    def __init__(self, files):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name)
        for name, (content, executable) in files.items():
            target = self.path / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            target.chmod(0o755 if executable else 0o644)

    def __enter__(self):
        return self.path

    def __exit__(self, *exception):
        self.directory.cleanup()


class RequiredFloorTests(unittest.TestCase):
    def required(self, files):
        with Tree(files) as tree:
            result = run("bobine_glibc_required", str(tree))
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def test_the_highest_symbol_wins_by_version_not_by_text(self):
        files = {"bin/app": (b"\x7fELF GLIBC_2.9 GLIBC_2.38 GLIBC_2.17", True), "lib/libx.so.1": (b"GLIBC_2.34", False)}
        self.assertEqual(self.required(files), "2.38")

    def test_three_part_versions_are_read(self):
        self.assertEqual(self.required({"bin/app": (b"GLIBC_2.2.5 GLIBC_2.3", True)}), "2.3")

    def test_only_executables_and_shared_libraries_count(self):
        files = {"bin/app": (b"GLIBC_2.30", True), "share/notes.txt": (b"GLIBC_2.99", False)}
        self.assertEqual(self.required(files), "2.30")

    def test_default_without_any_symbol(self):
        self.assertEqual(self.required({"share/readme": (b"nothing", False)}), "2.17")


class CheckTests(unittest.TestCase):
    def check(self, content, declared):
        with Tree({"bin/app": (content, True)}) as tree, tempfile.TemporaryDirectory() as folder:
            floor_file = Path(folder, "MIN_GLIBC")
            floor_file.write_text(declared + "\n", encoding="utf-8")
            return run("bobine_glibc_check", str(tree), floor_file=floor_file)

    def test_binaries_within_the_floor_print_the_declared_floor(self):
        result = self.check(b"GLIBC_2.34", "2.38")
        self.assertEqual((result.returncode, result.stdout.strip()), (0, "2.38"), result.stderr)

    def test_binaries_above_the_floor_fail_with_an_explanation(self):
        result = self.check(b"GLIBC_2.39", "2.38")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("2.39", result.stderr)
        self.assertIn("MIN_GLIBC", result.stderr)

    def test_version_order_is_numeric(self):
        """2.9 is older than 2.38: a text comparison would reject binaries that fit."""
        self.assertEqual(self.check(b"GLIBC_2.9", "2.38").returncode, 0)


class DebControlTests(unittest.TestCase):
    def inject(self, control):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder, "control")
            path.write_text(control, encoding="utf-8")
            result = run("bobine_deb_require_glibc", str(path), DECLARED)
            return result, path.read_text(encoding="utf-8")

    def test_libc6_comes_first_in_the_real_control_file(self):
        result, text = self.inject((ROOT / "packaging/linux/DEBIAN/control").read_text(encoding="utf-8"))
        self.assertEqual(result.returncode, 0, result.stderr)
        depends = re.search(r"^Depends: (.*)$", text, re.M).group(1)
        self.assertTrue(depends.startswith(f"libc6 (>= {DECLARED}), "), depends)
        self.assertIn("polkitd", depends, "the other dependencies must be kept")

    def test_a_control_file_without_depends_is_refused(self):
        result, _ = self.inject("Package: bobine\n")
        self.assertNotEqual(result.returncode, 0)


class WiringTests(unittest.TestCase):
    def test_both_packages_use_the_shared_floor(self):
        deb = (ROOT / "packaging/linux/build_deb.sh").read_text(encoding="utf-8")
        rpm = (ROOT / "packaging/rpm/build_rpm.sh").read_text(encoding="utf-8")
        for name, script in (("deb", deb), ("rpm", rpm)):
            with self.subTest(package=name):
                self.assertIn("glibc_floor.sh", script)
                self.assertIn("bobine_glibc_check", script)
        self.assertIn("bobine_deb_require_glibc", deb)

    def test_the_declared_floor_is_a_plain_version(self):
        self.assertRegex(DECLARED, r"^\d+\.\d+$")

    def test_readmes_state_the_declared_floor(self):
        for name in ("README.md", "README.fr.md"):
            with self.subTest(document=name):
                self.assertIn(f"glibc {DECLARED}", (ROOT / name).read_text(encoding="utf-8"))

    @unittest.skipUnless(NOTES_SCRIPT.exists(), "the rolling release notes are not on this branch yet")
    def test_rolling_notes_state_the_declared_floor(self):
        spec = importlib.util.spec_from_file_location("render_rolling_notes_for_floor", NOTES_SCRIPT)
        renderer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(renderer)
        self.assertIn(f"glibc {DECLARED}", renderer.render("canary"))


if __name__ == "__main__":
    unittest.main()
