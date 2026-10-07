# Contributing to Bobine

Thank you for considering a contribution. Bobine runs unattended in gyms and studios, on hardware its maintainer cannot always reach: a regression is not an inconvenience, it is a class that does not start. The standards below follow from that. They are strict because the software is relied upon, not to discourage you.

French version: [docs/fr/CONTRIBUTING.md](docs/fr/CONTRIBUTING.md). By taking part you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md). Vulnerabilities are not reported through issues or pull requests: see [SECURITY.md](SECURITY.md).

## Before you start

- Search existing issues and pull requests first.
- For anything beyond a small, obvious fix (new feature, behavior change, refactoring, new dependency), open an issue and agree on the approach before writing code. Unsolicited large pull requests are likely to be declined, whatever their quality.
- Keep each pull request to one logical change. A bug fix does not carry a refactoring, and a refactoring does not carry a feature.
- Issues and pull requests may be written in English or French.

## Principles

**Evidence, not assumption.** A problem is understood when you can reproduce it and point to its cause. A fix is correct when you can show that it removes that cause. Back your claims with facts: logs, error messages, versions, exact reproduction steps, measurements. "It should work" and "this probably fixes it" are not acceptable in a pull request.

**Root cause, not symptom.** Do not mask an error with a silent `try`/`except`, a retry, a sleep, or a special case that hides the real failure. If the underlying design is at fault, say so and propose to fix it there.

**Say what you did not verify.** State precisely what you tested, on which system and version, and what you could not test. An honest gap is welcome; an unverified claim presented as fact is not.

**Respect the architecture.** Read [`docs/ARCHITECTURE.en.md`](docs/ARCHITECTURE.en.md) before touching the backend, the data model or the network contract. Bobine runs as a single process (FastAPI and SQLite) and works fully offline. A change that adds an external service, a cloud dependency or a new background component needs prior agreement in an issue.

**Accuracy in documentation.** Never document a feature that does not exist or is not released. User-facing documentation lives in `README.md` and `README.fr.md`; keep the two consistent, and tell us if you cannot provide a translation.

## You are responsible for your code

Whatever tools you use to write code, you are the author of what you submit, and you answer for it.

- You must be able to explain every line of your change and why it is there, without help, during review.
- You must have run it. A pull request describing tests that were not executed, or referring to functions, options or files that do not exist, will be closed.
- You must have the right to license it. Do not submit code copied from a source whose license is incompatible with the AGPL-3.0, and verify the provenance of any large block you did not write yourself, including output from code generators.
- You must follow the project's conventions and style, and strip what adds no value: boilerplate comments, restated code, unrelated reformatting, speculative abstractions, padded descriptions.
- A pull request that shows no sign of human review (unrelated changes, invented references, generic prose, code that does not fit the codebase) is closed without detailed feedback.
- Automated or bulk submissions (scripts opening pull requests, mass reformatting, mass dependency changes) are not accepted without prior agreement. Dependency updates are handled by the maintainer.

Maintainers review contributions in their own time. Making the review short is your responsibility.

## Development setup

Bobine has three components. Before opening a pull request, run locally the checks below for each component you touched. CI runs the same ones.

| Component | Directory | Checks |
|---|---|---|
| Backend (Python, FastAPI, SQLite) | `backend/` | `python -m compileall -q backend/app scripts` then `python -m unittest discover -s backend/tests` (needs `ffmpeg`; CI uses Python 3.12) |
| Frontend (Next.js, Node 22) | `frontend/` | `npm ci` then `npm run build` (CI). `npm run lint` is not enforced by CI and reports existing issues: do not introduce new ones in the code you touch |
| Assistant (Rust, Tauri) | `assistant/` | `cargo clippy --workspace --all-targets -- -D warnings` then `cargo test --workspace` |

The data schema is managed by SQLAlchemy: tables are created at startup, and columns added to existing tables go through the idempotent micro-migrations of the database module (see the architecture document). A schema change must work on an existing database without data loss and be covered by a test. A pull request that breaks one of the CI jobs is not reviewed until it is green.

## Platforms

Bobine targets five execution profiles: Android (ARM64), Linux desktop, a headless Debian appliance, Windows and macOS. A change that touches system behavior (hardware detection, power and sleep, windowing, audio and video output, storage, processes, networking, packaging) must be reasoned about for each profile, and your pull request must state which ones you tested and which you did not. If you can only test on one system, say so: the maintainer will cover the others.

## Tests

- A bug fix includes a regression test whenever the bug can be reproduced in an automated test, and the test must fail without your fix.
- New behavior includes tests for its normal path and its failure modes.
- When automated testing is not practical (hardware, display, packaging), describe the manual procedure you followed and its result.

## Commits

Bobine uses [Conventional Commits](https://www.conventionalcommits.org/), in lowercase, with a scope:

```
type(scope): short description in the imperative mood
```

| Type | Use |
|---|---|
| `feat` | a user-visible feature |
| `fix` | a bug fix |
| `refactor` | a change with no behavior change |
| `perf` | a measured performance improvement |
| `test` | tests only |
| `docs` | documentation only |
| `build`, `ci`, `chore` | packaging, pipelines, maintenance |
| `revert` | reverting a previous commit |

The scope names the area (`coach`, `playlists`, `audio`, `schedule`, `updates`, `packaging`, `assistant`, `android`, `windows`, `security`, `ci`...). Examples taken from the history:

```
fix(android): synchroniser wired_display_mode sur la detection HDMI reelle
fix(security): zip-slip audio/radio, fail-closed maj desktop, dependabot
feat(updates): unification et fiabilisation de la mise a jour automatique multi-os
```

- The subject is short, specific and states what changes, not how you felt about it. Messages may be in English or French, consistently within a pull request.
- For anything non-trivial, add a body as a bulleted list: the root cause that was resolved, the mechanism introduced, and how it was tested.
- One logical change per commit; every commit must build and pass the tests on its own. Do not leave fixup, "wip" or "address review" commits in the final history.
- Keep your branch current by rebasing on `main` rather than merging `main` into it.
- Never commit secrets, credentials, personal data, media files, real hostnames or IP addresses, or generated artifacts. Check your diff, screenshots and logs before pushing.

## Pull requests

Open the pull request against `main`. The description must contain:

1. **What and why**: the problem, with the issue number if there is one.
2. **How**: the approach, and the alternatives you rejected when relevant.
3. **Verification**: the exact commands you ran and their result, plus the manual steps and the platforms covered (see above).
4. **Risks**: what could regress, and how someone would notice.
5. **Documentation**: what you updated, or why nothing needed updating.

Do not change `VERSION` or the files under `docs/releases/`: releases are prepared by the maintainer. Reply to review comments on the thread, and push changes as new commits until the review ends, then clean up the history as agreed.

A pull request is merged when CI is green, the review is complete and the change fits the project's direction. A decision not to merge is about the change, not about you; the reason is given.

## Dependencies

Adding a dependency requires a justification in the pull request: what it does, why the standard library or an existing dependency is not enough, its license (compatible with the AGPL-3.0), its maintenance status and its footprint on a small appliance. The runtime must remain usable without internet access.

## Licensing

Bobine is released under the [GNU AGPL-3.0](LICENSE). By submitting a contribution you declare that you have the right to do so and agree that it is distributed under the same license.

## Document history

| Date | Change |
|---|---|
| 2026-10-08 | Contribution guide adopted. |
