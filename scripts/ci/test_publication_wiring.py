"""Wiring of the publication jobs: in-place rolling releases, one publisher per channel, guarded order, scheduled refresh."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
CI = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
REFRESH = (ROOT / ".github/workflows/refresh-package-repositories.yml").read_text(encoding="utf-8")


def job(name):
    match = re.search(rf"^  {re.escape(name)}:\n(.*?)(?=^  [a-z][a-z0-9-]*:\n|\Z)", CI, re.S | re.M)
    assert match, name
    return match.group(1)


class RollingReleaseTests(unittest.TestCase):
    def test_no_job_deletes_a_release(self):
        self.assertNotIn("gh release delete", CI)
        self.assertNotIn("gh release create", CI)

    def test_each_rolling_job_publishes_in_place_behind_the_guard(self):
        for channel in ("canary", "beta"):
            text = job(f"release-{channel}")
            self.assertIn(f"bash scripts/ci/publish-rolling-release.sh {channel} release-assets", text)
            guard, move, publish = (text.index(marker) for marker in ("id: guard", f'Force-move the "{channel}" tag', f"Publish {channel.capitalize()} release"))
            self.assertLess(guard, move)
            self.assertLess(move, publish)
            for step in (f'Force-move the "{channel}" tag', "id: notes", f"Publish {channel.capitalize()} release"):
                block = text[text.index(step):]
                self.assertIn("steps.guard.outputs.publish == 'true'", block[:block.index("run:")], step)
            self.assertIn("published: ${{ steps.guard.outputs.publish }}", text)

    def test_each_channel_publishes_one_run_at_a_time(self):
        groups = []
        for channel in ("canary", "beta"):
            text = job(f"release-{channel}")
            group = re.search(r"concurrency:\n\s+group: (\S+)\n\s+cancel-in-progress: false", text)
            self.assertTrue(group, channel)
            groups.append(group.group(1))
        self.assertEqual(len(set(groups)), 2)

    def test_only_the_canary_must_be_the_tip_of_main_and_only_from_main(self):
        canary, beta = job("release-canary"), job("release-beta")
        self.assertIn("--require-tip origin/main", canary)
        self.assertIn('[ "$GITHUB_REF" = refs/heads/main ]', canary)
        self.assertNotIn("--require-tip", beta)


class PackageRepositoryPublicationTests(unittest.TestCase):
    def test_repositories_are_published_only_for_a_release_the_guard_accepted(self):
        condition = re.search(r"  publish-linux-packages:.*?\n    if: \|\n(.*?)\n    runs-on", CI, re.S).group(1)
        self.assertIn("needs.release-canary.outputs.published == 'true'", condition)
        self.assertIn("needs.release-beta.outputs.published == 'true'", condition)

    def test_the_final_push_retries_with_a_rebase(self):
        text = job("publish-linux-packages")
        self.assertIn("bash scripts/ci/commit-package-repository.sh package-repo", text)
        self.assertNotIn("git push origin gh-pages", text)

    def test_the_repository_tests_have_the_tool_they_need(self):
        self.assertIn("apt-get install -y -qq --no-install-recommends reprepro", job("version"))


class ScheduledRefreshTests(unittest.TestCase):
    def test_it_runs_every_week_and_can_be_started_by_hand(self):
        self.assertRegex(REFRESH, r"schedule:\n\s+- cron: '\d+ \d+ \* \* \d'")
        self.assertIn("workflow_dispatch:", REFRESH)

    def test_a_manual_run_is_a_dry_run_unless_unchecked(self):
        self.assertRegex(REFRESH, r"dry_run:(?:.|\n)*?default: true")
        self.assertIn("DRY_RUN: ${{ github.event_name == 'workflow_dispatch' && inputs.dry_run }}", REFRESH)

    def test_it_never_writes_at_the_same_time_as_a_publication(self):
        self.assertRegex(REFRESH, r"concurrency:\n\s+group: publish-linux-packages\n\s+cancel-in-progress: false")
        self.assertIn("group: publish-linux-packages", job("publish-linux-packages"))

    def test_it_refreshes_then_verifies_then_publishes_with_the_shared_script(self):
        order = [REFRESH.index(marker) for marker in ("refresh-apt-release.sh package-repo", "verify-packages.py package-repo", "commit-package-repository.sh package-repo")]
        self.assertEqual(order, sorted(order))


class HealthProbeTests(unittest.TestCase):
    PROBE = (ROOT / ".github/workflows/probe-package-repositories.yml").read_text(encoding="utf-8")

    def test_it_runs_every_day_without_any_secret(self):
        self.assertRegex(self.PROBE, r"schedule:\n\s+- cron: '\d+ \d+ \* \* \*'")
        self.assertNotIn("secrets.", self.PROBE)
        self.assertIn("contents: read", self.PROBE)

    def test_it_compares_both_rolling_channels_with_their_release(self):
        for channel in ("canary", "beta"):
            self.assertIn(f'--release {channel}="$RUNNER_TEMP/{channel}.json"', self.PROBE)


if __name__ == "__main__":
    unittest.main()
