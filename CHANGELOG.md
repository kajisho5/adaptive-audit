# Changelog

Versions are tracked in `VERSION` at the repo root and tagged on `main` by
`.github/workflows/release.yml` whenever `VERSION` changes (a git tag +
GitHub Release, created with auto-generated notes from the commits since
the previous tag).

**This is bookkeeping, not a package release.** adaptive-audit isn't
published to npm, PyPI, or any public Claude Code plugin marketplace
listing — bumping `VERSION` here doesn't push anything out on its own, and
someone who installed via a plain `.claude/skills/` copy (see README
"Usage") still has to re-copy by hand. It mainly gives this project's own
history a stable marker to refer to (in this file, in issues, in
conversation) instead of a bare commit hash.

Since 0.1.0, this repo can also be self-hosted as a personal/third-party
Claude Code marketplace (`.claude-plugin/marketplace.json` — see README
"Install as a plugin"), which *does* give an installed copy a real update
path (`/plugin marketplace update`). Keep that file's plugin `version`
field in sync with this one — `tests/test_versioning.py` enforces it.

## [Unreleased]

- Added `LICENSE` (MIT) and `CONTRIBUTING.md` — both were missing, which
  blocked this repo from actually being usable as OSS despite the plugin
  marketplace distribution path already documented in this README.
- README: added a "How this compares to existing tools" section stating
  plainly, not just via a linked research doc, that a security-only need is
  already well covered by `cloudflare/security-audit-skill` or
  `dinosn/raptor-loop-hunt`, and that the Remediate step is not part of this
  project's differentiation (it overlaps with Anthropic's own
  `/security-review` and Snyk's official Claude Skill).
- `scripts/receipts.py` (both copies): documented that `_debt_status`'s
  STALE/AGING thresholds (3/2 runs) are a disclosed, uncalibrated heuristic,
  not a measured constant — a prior gap where the reasoning existed only in
  a reviewer's head, not in the code.
- `adaptive-audit-execute` step 6 (Remediate): two more real trials (iteration
  21), closing two of the three gaps iteration 20 left open — a PR request
  against a repo with no remote at all, and a first non-Python (Go) target.
  Both found real wording gaps, both fixed directly in `SKILL.md`: step 6.4
  now states that a requested end-state 6.2 already found impossible (e.g.
  no remote to push to) does not retroactively authorize a lesser
  unrequested action like committing locally; step 6.3 now generalizes the
  "a regression test must be shown to have the power to catch the bug, not
  just assumed to" principle to concurrency findings specifically (verify
  the new test fails against the unfixed code, via the ecosystem's race
  detector, before trusting it against the fix), stated as the same
  underlying principle as the performance case rather than a one-off carve
  out. Still not validated: fixing more than one finding in the same turn.
- `adaptive-audit-execute` step 6 (Remediate) validated with a real subagent
  trial against a disposable copy of the `cli-data-processor` fixture (see
  `evals/validation-notes.md` iteration 20) — the fix itself worked
  correctly (O(n·m) → O(n+m), ~500x faster, verified with a benchmark and a
  new regression test, nothing staged or committed). The trial found two
  real wording gaps, both fixed directly in `SKILL.md` from that evidence:
  6.2's "state this up front" is now explicit that it must be its own
  message sent before any file is touched, not folded into the completion
  report; 6.3 now says to prefer a structural regression test over a flaky
  timing assertion for performance/complexity findings specifically.
- `adaptive-audit-execute`: a new opt-in Remediate step (step 6), triggered
  only by a separate, explicit follow-up request after an audit ("直して",
  "直してPRにして") — never inferred from a finding's severity or an audit's
  own `overall_status`. Fixes CONFIRMED findings minimally (one at a time,
  scoped to each finding's own `failure_scenario`), adds/runs tests where a
  test runner exists, and never commits or pushes without being asked to.
  Checks and discloses up front whether this session can actually write to
  the target project and, if a PR was asked for, whether it can push to or
  open a PR against that remote — surfacing a missing push credential before
  writing anything, not after. Does not write to `receipts.py`: a fix is not
  the same claim as re-verifying a domain's audit debt.

## [0.1.0] — first tracked release

The first version tag, covering everything merged up to this point (PR #1
and PR #8) — this project didn't track versions before now, so this entry
is retroactive, not a description of what changed since some prior tag.

- Two Claude Code Skills: `adaptive-audit-plan` (scoping) and
  `adaptive-audit-execute` (the default: scopes and then actually runs the
  audit in one response).
- Cross-run audit-debt tracking (`scripts/receipts.py`), now covered by an
  automated pytest suite (`tests/`, run in CI via
  `.github/workflows/test.yml`) rather than only hand-run evals.
- Domain-agnostic Hunt → Verify execution under true cross-agent isolation,
  audit-plan self-verification (an isolated critic reviews the plan before
  it ships), staged Quick→Standard/Deep depth escalation for
  `depth_confidence: provisional` domains, and invariant extraction (opt-in,
  validated across 4 trials on real and synthetic projects).
- A diff-scoped re-audit option (`adaptive-audit-plan` step 0.5) that asks
  the person to choose between a cheap diff-only pass and a full re-audit
  when a prior full audit exists and the change since is clearly small,
  rather than deciding silently.
- A local-checkout freshness check (step 0.4): `git fetch` (never
  `git pull`) before scoping a plan, warning and asking before proceeding
  if the checkout is behind its remote.
- An explicit, opt-in-only exception allowing `adaptive-audit-execute` to
  save its findings report into the audited project itself
  (`docs/audit-reports/`), with an explicit warning before committing a
  report containing an unpatched security finding.
- `.claude-plugin/marketplace.json`, letting this repo be installed and
  actually updated as a Claude Code plugin (`/plugin marketplace add
  kajisho5/adaptive-audit`, `/plugin install adaptive-audit@adaptive-audit`,
  `/plugin marketplace update adaptive-audit`) as an alternative to the
  plain manual-copy install — auto-invocation by request ("バグチェックして")
  works identically either way.
- Validated across several real, third-party projects (not just synthetic
  fixtures) — full history in `evals/validation-notes.md`.
- Full GitHub repo automation: a single-job release workflow that resolves
  the next version from merged-PR labels via `release-drafter` (dry-run),
  respects a manual `VERSION` bump instead of overwriting it, updates
  `VERSION`/`CHANGELOG.md`/`marketplace.json` and creates the tag + GitHub
  Release in one run (no tag-push-triggered second workflow, since a push
  made with the default `GITHUB_TOKEN` never triggers another run); PR
  autolabeling so that resolution has real labels to read; Dependabot
  (`github-actions` only — see `.github/dependabot.yml` for why fixture
  ecosystems are deliberately excluded); CodeQL scoped to this repo's own
  Python source (`scripts/`, `receipts.py` copies, `tests/`), explicitly
  excluding `evals/fixtures/**`'s deliberately-vulnerable synthetic
  projects; a PR template matching this repo's actual Summary/Test plan
  convention; and `SECURITY.md` pointing at GitHub's private vulnerability
  reporting flow.
