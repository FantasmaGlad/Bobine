"""Publishing to gh-pages stages the root .repo aliases and survives a concurrent push (rebase and retry)."""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/ci/commit-package-repository.sh"
PREPARE = ROOT / "scripts/ci/prepare-package-repository.sh"


def git(cwd, *args, check=True):
    result = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.org", *args], cwd=cwd, capture_output=True, text=True)
    if check and result.returncode:
        raise AssertionError(result.stderr)
    return result.stdout.strip()


class CommitPackageRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        base = Path(self.directory.name)
        self.remote = base / "remote.git"
        git(base, "init", "-q", "--bare", "-b", "gh-pages", str(self.remote))
        self.work = self.clone(base / "work")
        (self.work / "index.html").write_text("portal v1")
        (self.work / "debian").mkdir()
        (self.work / "debian/Release").write_text("release v1")
        for name in ("latest.json", "mirror-packages.json", "bobine.gpg"):
            (self.work / name).write_text(name)
        git(self.work, "add", "-A")
        git(self.work, "commit", "-q", "-m", "init")
        git(self.work, "push", "-q", "origin", "HEAD:gh-pages")
        self.other = self.clone(base / "other")
        self.base = base

    def clone(self, path):
        git(path.parent, "clone", "-q", str(self.remote), str(path))
        git(path, "checkout", "-q", "-B", "gh-pages")
        return path

    def run_script(self, message="chore: publish", **environment):
        env = dict(os.environ, PUSH_RETRY_DELAY="0", **environment)
        return subprocess.run(["bash", str(SCRIPT), str(self.work), message], capture_output=True, text=True, env=env)

    def remote_files(self):
        return set(git(self.remote, "ls-tree", "-r", "--name-only", "gh-pages").splitlines())

    def test_root_repo_aliases_are_committed_and_pushed(self):
        for name in ("bobine.repo", "bobine-stable.repo", "bobine-beta.repo", "bobine-canary.repo"):
            (self.work / name).write_text("[repo]")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue({"bobine.repo", "bobine-stable.repo", "bobine-beta.repo", "bobine-canary.repo"} <= self.remote_files())

    def test_the_aliases_written_by_the_repository_script_are_all_published(self):
        written = set(re.findall(r'"\$destination/(bobine[^"]*\.repo)"', PREPARE.read_text(encoding="utf-8")))
        written = {name.replace("$suite", suite) for name in written for suite in ("stable", "beta", "canary")}
        self.assertIn("bobine.repo", written)
        published = SCRIPT.read_text(encoding="utf-8")
        for name in sorted(written):
            self.assertIn(name, published, f"{name} est écrit à la racine mais jamais ajouté au commit")

    def test_showcase_pages_are_not_swept_into_the_commit(self):
        (self.work / "index.html").write_text("portal edited locally")
        (self.work / "debian/Release").write_text("release v2")
        self.assertEqual(self.run_script().returncode, 0)
        self.assertEqual(git(self.remote, "show", "gh-pages:index.html"), "portal v1")
        self.assertEqual(git(self.remote, "show", "gh-pages:debian/Release"), "release v2")

    def test_nothing_to_publish_makes_no_commit(self):
        before = git(self.remote, "rev-parse", "gh-pages")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(git(self.remote, "rev-parse", "gh-pages"), before)
        self.assertIn("Aucun changement", result.stdout)

    def test_a_concurrent_push_on_other_files_is_rebased_over(self):
        (self.other / "index.html").write_text("portal v2")
        git(self.other, "commit", "-q", "-am", "portal")
        git(self.other, "push", "-q", "origin", "HEAD:gh-pages")
        (self.work / "debian/Release").write_text("release v2")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(git(self.remote, "show", "gh-pages:index.html"), "portal v2")
        self.assertEqual(git(self.remote, "show", "gh-pages:debian/Release"), "release v2")
        self.assertEqual(git(self.remote, "rev-list", "--count", "gh-pages"), "3")
        self.assertIn("rebase", result.stderr)

    def test_a_conflicting_push_fails_cleanly_and_loses_nothing(self):
        (self.other / "debian/Release").write_text("release from elsewhere")
        git(self.other, "commit", "-q", "-am", "elsewhere")
        git(self.other, "push", "-q", "origin", "HEAD:gh-pages")
        (self.work / "debian/Release").write_text("release v2")
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(git(self.remote, "show", "gh-pages:debian/Release"), "release from elsewhere")
        self.assertFalse((self.work / ".git/rebase-merge").exists())
        self.assertFalse((self.work / ".git/rebase-apply").exists())

    def test_the_number_of_attempts_is_bounded(self):
        hook = self.remote / "hooks/pre-receive"
        hook.write_text("#!/bin/sh\nexit 1\n")
        hook.chmod(0o755)
        (self.work / "debian/Release").write_text("release v2")
        result = self.run_script(PUSH_ATTEMPTS="2")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stderr.count("Poussée refusée"), 1)
        self.assertIn("après 2 essais", result.stderr)

    def test_dry_run_commits_locally_and_pushes_nothing(self):
        before = git(self.remote, "rev-parse", "gh-pages")
        (self.work / "debian/Release").write_text("release v2")
        result = self.run_script(DRY_RUN="true")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(git(self.remote, "rev-parse", "gh-pages"), before)
        self.assertEqual(git(self.work, "log", "-1", "--format=%s"), "chore: publish")


if __name__ == "__main__":
    unittest.main()
