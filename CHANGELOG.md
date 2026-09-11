# Changelog

Versions are tracked in `VERSION` at the repo root and tagged on `main` by
`.github/workflows/release.yml` whenever `VERSION` changes (a git tag +
GitHub Release, created with auto-generated notes from the commits since
the previous tag).

**This is bookkeeping, not a package release.** adaptive-audit isn't
published to npm, PyPI, or the Claude Code plugin marketplace — it's copied
by hand into `.claude/skills/`. Bumping `VERSION` here does not update
anyone's local copy; it only gives this project's own history a stable
marker to refer to (in this file, in issues, in conversation) instead of a
bare commit hash. See the README's "Cost" section and
`research/adaptive-audit-competitive-research.md` §9 for why marketplace
distribution (which would make version bumps meaningful to installed
copies) was deliberately not pursued.

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
- Validated across several real, third-party projects (not just synthetic
  fixtures) — full history in `evals/validation-notes.md`.

## [Unreleased]

Nothing yet.
