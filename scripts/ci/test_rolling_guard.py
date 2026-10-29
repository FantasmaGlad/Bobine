"""The rolling-channel guard refuses to publish a build older than the one already published."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).with_name("rolling-guard.py")
SPEC = importlib.util.spec_from_file_location("rolling_guard", SCRIPT)
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


class DecisionTests(unittest.TestCase):
    """decide() on plain values: `ancestor` says whether the first commit is an ancestor of the second."""
    OLD, MID, NEW = "a" * 40, "b" * 40, "c" * 40
    order = [OLD, MID, NEW]

    def ancestor(self, a, b):
        return self.order.index(a) <= self.order.index(b)

    def decide(self, sha, tip=None, published=None, event="push", attempt=1):
        return guard.decide(sha, tip, published, event, attempt, self.ancestor)

    def test_first_publication_is_allowed(self):
        self.assertTrue(self.decide(self.MID)[0])

    def test_newer_build_is_allowed(self):
        self.assertTrue(self.decide(self.NEW, tip=self.NEW, published=self.MID)[0])

    def test_same_commit_can_be_republished(self):
        self.assertTrue(self.decide(self.MID, tip=self.MID, published=self.MID)[0])

    def test_a_rerun_of_an_old_run_is_refused(self):
        self.assertFalse(self.decide(self.OLD, published=self.MID, attempt=2)[0])
        self.assertFalse(self.decide(self.OLD, published=self.MID, event="push")[0])

    def test_a_commit_that_is_no_longer_the_tip_is_refused(self):
        publish, reason = self.decide(self.MID, tip=self.NEW)
        self.assertFalse(publish)
        self.assertIn("tête", reason)

    def test_a_fresh_manual_run_may_go_back_on_purpose(self):
        publish, reason = self.decide(self.OLD, published=self.MID, event="workflow_dispatch", attempt=1)
        self.assertTrue(publish)
        self.assertIn("volontaire", reason)

    def test_a_rerun_of_a_manual_run_may_not_go_back(self):
        self.assertFalse(self.decide(self.OLD, published=self.MID, event="workflow_dispatch", attempt=2)[0])


class GitFixture(unittest.TestCase):
    """A real repository: three commits on main, one commit on a side branch, a movable canary tag."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.repo = Path(self.directory.name)
        self.git("init", "-q", "-b", "main")
        self.commits = []
        for number in range(3):
            self.commits.append(self.commit(f"c{number}"))
        self.git("update-ref", "refs/remotes/origin/main", self.commits[2])
        self.git("checkout", "-q", "-b", "side", self.commits[0])
        self.side = self.commit("side")
        self.git("checkout", "-q", "main")

    def git(self, *args):
        result = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.org", *args], cwd=self.repo, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def commit(self, name):
        (self.repo / name).write_text(name)
        self.git("add", name)
        self.git("commit", "-q", "-m", name)
        return self.git("rev-parse", "HEAD")

    def run_guard(self, sha, *extra, event="push", attempt="1", tag="canary"):
        output = self.repo / "github-output"
        output.write_text("")
        environment = dict(os.environ, GITHUB_OUTPUT=str(output))
        result = subprocess.run(["python3", str(SCRIPT), "--tag", tag, "--sha", sha, "--event", event, "--attempt", attempt, *extra],
                                cwd=self.repo, capture_output=True, text=True, env=environment)
        values = dict(line.split("=", 1) for line in output.read_text().splitlines() if "=" in line)
        return result, values


class GuardCommandTests(GitFixture):
    def test_no_tag_yet_publishes_the_tip(self):
        result, values = self.run_guard(self.commits[2], "--require-tip", "origin/main")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(values["publish"], "true")

    def test_old_run_rerun_after_the_tag_moved_is_refused(self):
        self.git("tag", "canary", self.commits[2])
        result, values = self.run_guard(self.commits[1], "--require-tip", "origin/main", attempt="2")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(values["publish"], "false")

    def test_older_commit_without_require_tip_is_refused_by_ancestry(self):
        self.git("tag", "canary", self.commits[2])
        self.assertEqual(self.run_guard(self.commits[0])[1]["publish"], "false")

    def test_a_commit_off_the_published_line_is_not_an_older_build(self):
        self.git("tag", "canary", self.commits[2])
        self.assertEqual(self.run_guard(self.side)[1]["publish"], "true")

    def test_manual_run_from_a_branch_is_not_bound_to_the_tip_of_main(self):
        self.assertEqual(self.run_guard(self.side, event="workflow_dispatch")[1]["publish"], "true")

    def test_each_channel_reads_its_own_tag(self):
        self.git("tag", "canary", self.commits[2])
        self.assertEqual(self.run_guard(self.commits[0], tag="beta")[1]["publish"], "true")

    def test_missing_tip_reference_is_an_error_not_a_blind_publication(self):
        result, values = self.run_guard(self.commits[2], "--require-tip", "origin/nope")
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("publish", values)

    def test_unknown_commit_is_an_error(self):
        result, values = self.run_guard("f" * 40)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("publish", values)


if __name__ == "__main__":
    unittest.main()
