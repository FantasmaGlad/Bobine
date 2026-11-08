"""Wiring of the publication jobs: in-place rolling releases, one publisher per channel, guarded order, scheduled refresh."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
CI = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
REFRESH = (ROOT / ".github/workflows/refresh-package-repositories.yml").read_text(encoding="utf-8")
ROLLING_ACTION = (ROOT / ".github/actions/publish-rolling-release/action.yml").read_text(encoding="utf-8")
ASSEMBLE_ACTION = (ROOT / ".github/actions/assemble-release-assets/action.yml").read_text(encoding="utf-8")


def job(name):
    match = re.search(rf"^  {re.escape(name)}:\n(.*?)(?=^  [a-z][a-z0-9-]*:\n|\Z)", CI, re.S | re.M)
    assert match, name
    return match.group(1)


class RollingReleaseTests(unittest.TestCase):
    def test_no_job_deletes_a_release(self):
        self.assertNotIn("gh release delete", CI)
        self.assertNotIn("gh release create", CI)

    def test_each_rolling_job_publishes_through_the_shared_action(self):
        for channel in ("canary", "beta"):
            text = job(f"release-{channel}")
            self.assertIn("uses: ./.github/actions/publish-rolling-release", text)
            self.assertIn(f"channel: {channel}", text)
            self.assertIn("uses: ./.github/actions/assemble-release-assets", text)
            self.assertIn(f"suffix: {channel}", text)
            self.assertLess(text.index("assemble-release-assets"), text.index("publish-rolling-release"))
            self.assertIn("published: ${{ steps.rolling.outputs.published }}", text)
            self.assertIn("fetch-depth: 0", text)  # le changelog et la garde lisent l'historique

    def test_the_shared_action_publishes_in_place_behind_the_guard(self):
        text = ROLLING_ACTION
        guard, move, notes, publish = (text.index(marker) for marker in (
            "id: guard", "Force-move the mobile tag", "id: notes", "- name: Publish release"))
        self.assertLess(guard, move)
        self.assertLess(move, notes)
        self.assertLess(notes, publish)
        for step in ("Force-move the mobile tag", "id: notes", "- name: Publish release"):
            block = text[text.index(step):]
            self.assertIn("steps.guard.outputs.publish == 'true'", block[:block.index("run:")], step)
        self.assertIn("value: ${{ steps.guard.outputs.publish }}", text)
        self.assertIn('bash scripts/ci/publish-rolling-release.sh "$CHANNEL" release-assets', text)
        self.assertNotIn("gh release delete", text)
        self.assertNotIn("continue-on-error", text)

    def test_the_assembly_is_shared_and_strict(self):
        self.assertNotIn("continue-on-error", ASSEMBLE_ACTION)
        self.assertIn('scripts/ci/verify-release-assets.sh release-assets "$SUFFIX"', ASSEMBLE_ACTION)
        self.assertLess(ASSEMBLE_ACTION.index("Signer la liste des empreintes"), ASSEMBLE_ACTION.index("Vérifier la complétude"))
        self.assertIn("if: always()", ASSEMBLE_ACTION[ASSEMBLE_ACTION.index("Retirer la clé privée"):])
        stable = job("release-stable")
        self.assertIn("suffix: ${{ needs.version.outputs.filename_version }}", stable)
        self.assertIn("winget-tag: ${{ needs.version.outputs.tag_name }}", stable)
        for channel in ("canary", "beta"):
            self.assertNotIn("winget-tag", job(f"release-{channel}"))

    def test_the_three_publications_no_longer_duplicate_the_assembly(self):
        self.assertEqual(CI.count("Download Windows installer"), 0)
        self.assertEqual(CI.count("uses: ./.github/actions/assemble-release-assets") + CI.count("uses: ./.workflow-tools/.github/actions/assemble-release-assets"), 3)
        self.assertNotIn("continue-on-error", CI)

    def test_each_channel_publishes_one_run_at_a_time(self):
        groups = []
        for channel in ("canary", "beta"):
            text = job(f"release-{channel}")
            group = re.search(r"concurrency:\n\s+group: (\S+)\n\s+cancel-in-progress: false", text)
            self.assertTrue(group, channel)
            groups.append(group.group(1))
        self.assertEqual(len(set(groups)), 2)

    def test_bobine_deploy_n_est_plus_construit_ni_publie_ici(self):
        self.assertNotIn("assistant", CI.lower())

    def test_only_the_canary_must_be_the_tip_of_main_and_only_from_main(self):
        self.assertIn("require-tip: 'true'", job("release-canary"))
        self.assertIn("require-tip: 'false'", job("release-beta"))
        self.assertIn("--require-tip origin/main", ROLLING_ACTION)
        self.assertIn('[ "$GITHUB_REF" = refs/heads/main ]', ROLLING_ACTION)
        self.assertLess(ROLLING_ACTION.index('if [ "$REQUIRE_TIP" = true ]'), ROLLING_ACTION.index("--require-tip origin/main"))

    def test_the_stable_job_takes_its_actions_from_the_workflow_revision(self):
        """Republier un ancien tag Stable : l'action locale vient de la révision du workflow, pas du tag."""
        stable = job("release-stable")
        self.assertIn("path: .workflow-tools", stable)
        self.assertIn("uses: ./.workflow-tools/.github/actions/assemble-release-assets", stable)

    def test_rolling_notes_templates_exist_for_each_channel(self):
        for channel in ("canary", "beta"):
            template = (ROOT / f"scripts/ci/rolling-notes/{channel}.md").read_text(encoding="utf-8")
            self.assertIn("__COMMIT__", template)
            self.assertIn("__VERSION__", template)


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
        self.assertIn("apt-get $APT_OPTIONS install -y -qq --no-install-recommends reprepro", job("version"))


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
