# Contributing

## What lives where

- `adaptive-audit-plan/` and `adaptive-audit-execute/` are the two Claude Code
  Skills. Each is self-contained (per Claude Code Skill convention), which is
  why `scripts/receipts.py` is duplicated between them rather than shared.
  **The two copies must stay byte-identical** — `tests/test_receipts.py::test_scripts_stay_identical`
  enforces this in CI, so a fix or behavior change to one copy needs the same
  edit applied to the other in the same PR.
- `references/audit-domains.md` (also duplicated for the same reason) is the
  fixed 11-domain taxonomy both skills read from. Don't add a 12th domain
  ad hoc — see that file's own header for why (it would break the audit-debt
  comparability across runs).
- `evals/` holds synthetic fixture projects, eval prompts (`evals.json`), and
  hand-run validation notes (`validation-notes.md`). This is the only place
  `SKILL.md`'s actual LLM-driven behavior gets checked — see "Testing" below.
- `tests/` is the automated pytest suite for `scripts/receipts.py` and this
  repo's own release tooling (`scripts/bump_version.py`). Run in CI via
  `.github/workflows/test.yml`.
- `research/adaptive-audit-competitive-research.md` is the pre-implementation
  competitive analysis. If you're proposing a new capability, check whether
  it's already covered there before writing it up again.

## Testing

Two different kinds of test exist here, and they check different things:

1. **`scripts/receipts.py` and `scripts/bump_version.py`** are deterministic,
   non-LLM logic — the only parts of this project an automated suite can
   actually protect. Run:
   ```
   python3 -m pytest tests/ -v
   ```
   A PR touching either script must keep this passing, and must add a test
   for any new behavior rather than only manually verifying it once.

2. **`SKILL.md` behavior** (the actual Plan/Hunt/Verify/Remediate LLM
   reasoning) cannot be unit-tested — it's checked by running a real agent
   against the fixtures in `evals/fixtures/` and recording what actually
   happened in `evals/validation-notes.md`, following the existing
   iterations' format (method, headline result, what was and wasn't
   confirmed). A change to either `SKILL.md` that alters what the skill
   actually does should come with a new validation-notes.md entry, not just
   updated prose — a step with no recorded trial is, by this project's own
   standard, unverified.

## Adding a new SKILL.md step or option

- Match the existing style: every conditional branch states *why*, not just
  *what* (see any `SKILL.md` step for the pattern). A step that changes
  target-project files must say, explicitly, under what condition it's
  allowed to (opt-in, never inferred from severity/tone — see step 4.5 and
  step 6 in `adaptive-audit-execute/SKILL.md` for the established pattern).
- If it writes to `receipts.py`'s history, make sure it can't be confused
  with actually re-verifying a domain (see `adaptive-audit-execute` step
  6.5 for why Remediate deliberately does not touch it).
- Update `CHANGELOG.md`'s `[Unreleased]` section in the same PR.

## Vulnerability reports

For a security issue in this repository's own code (not a finding one of the
skills produced about some *other* project you audited), see `SECURITY.md`
— use GitHub's private vulnerability reporting flow, not a public issue.

## Fixtures under `evals/fixtures/`

These are frozen, deliberately-vulnerable synthetic projects used only to
validate the skills' own behavior. They are intentionally excluded from
Dependabot (`.github/dependabot.yml`) and CodeQL (`.github/workflows/codeql.yml`)
scanning — don't "fix" their vulnerabilities or "helpfully" update their
dependencies; that would break the eval they exist for.
