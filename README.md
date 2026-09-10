# adaptive-audit

> Status: **provisional**. Repository/skill names are working names, not final —
> see `research/adaptive-audit-competitive-research.md` for why.

Two Claude Code Skills, meant to be installed together:

- **`adaptive-audit-plan`** — given a natural-language request like
  "バグチェックして" or "check this for bugs", inspects the actual target
  project and produces a scoped, risk-aware **Audit Plan**: which audit domains
  actually matter here (security, correctness, performance, reliability,
  architecture, data-integrity, concurrency, dependency-health,
  configuration/deployment, test-coverage, observability), at what depth, and
  explicitly which domains were *not* selected and why. It also remembers, per
  project, which domains keep getting skipped across differently-framed
  requests over time, and surfaces that accumulated **audit debt** even when
  the current request doesn't mention it (`scripts/receipts.py report` renders
  this as a human-readable table, `export-csv` as CSV for Excel/Sheets — ask
  Claude to render a PDF from either when you need one to actually hand to
  someone, rather than that being a built-in, dependency-adding feature of the
  script itself). Before finalizing,
  an isolated critic subagent argues against the plan itself — mismatched
  depth, an exclusion whose stated reason doesn't hold up, a signal that maps
  to no domain — closing a gap nothing else in the competitive research does:
  verifying the *plan*, not only the findings.
- **`adaptive-audit-execute`** — carries an Audit Plan out: an isolated Hunt
  pass per selected domain, then a separate isolated Verify pass that
  independently checks each candidate against the source before it's reported
  (CONFIRMED / PLAUSIBLE / REJECTED), and records what was actually verified
  (not merely planned) back into the same history `adaptive-audit-plan` reads.

This is a narrower MVP of a larger "Adaptive Audit Engine" concept. Before
building the full pipeline, a competitive investigation found that most of the
individual pieces already exist in well-established OSS (notably
`cloudflare/security-audit-skill` and `dinosn/raptor-loop-hunt`, both
security/vulnerability-domain-locked), so this repo only implements the
confirmed white-space pieces, all now MVP-validated (see
`evals/validation-notes.md`):

1. **Domain-agnostic adaptive audit-plan generation** (`adaptive-audit-plan/SKILL.md`)
2. **Cross-audit-type persistent coverage/audit-debt tracking**
   (`adaptive-audit-plan/scripts/receipts.py`) — modeled on the
   `Artifact`/`ProductionReceipt` pattern from
   `kajisho5/AI-video-production-OS`'s `docs/SPEC.md`: one content-addressed
   record per completed run, kept outside the audited project. Debt is
   computed from what was actually *executed and verified*
   (`adaptive-audit-execute`'s results), not merely planned.
3. **Domain-agnostic Hunt → Verify execution** (`adaptive-audit-execute/SKILL.md`)
   — the general adversarial-review pattern proven by the security-specific
   tools above, re-implemented (not vendored) so it isn't locked to one domain.
   Validated under true cross-agent isolation (not a same-session fallback) on
   a fixture whose bugs aren't announced in comments — see
   `evals/validation-notes.md` iteration 4.
4. **Audit-plan self-verification** (`adaptive-audit-plan/SKILL.md` step 5) —
   an isolated critic reviews the plan itself before it ships. Confirmed
   nothing in the 22+ surveyed competitors does this; existing tools verify
   findings, not the plan that decided what to look for.

An experimental fifth idea — extracting a project's implied invariants ("a
task's owner must match the caller") and checking code against them directly,
rather than only scanning by domain — was tested once with promising but
early results (`adaptive-audit-execute/references/EXPERIMENTAL-invariant-extraction.md`).
It's deliberately **not** part of the default pipeline: this was the highest-risk,
least-proven idea in the original research (essentially unattempted anywhere in
the ecosystem), and one good run doesn't change that.

See `research/adaptive-audit-competitive-research.md` for the full competitive
analysis, feature matrix, and naming investigation behind these decisions.

## What's here

- `adaptive-audit-plan/` — the planning skill: `SKILL.md`,
  `references/audit-domains.md` (the fixed domain taxonomy), and
  `scripts/receipts.py`.
- `adaptive-audit-execute/` — the execution skill: `SKILL.md`, and its own
  copies of `references/audit-domains.md` and `scripts/receipts.py` (each
  skill folder is self-contained and independently copyable, per Claude Code
  Skill convention, even though the two are meant to be installed together —
  `receipts.py` is duplicated rather than shared across skill-folder
  boundaries for that reason).
- `evals/` — synthetic fixture projects, test prompts, and validation notes
  used to check both skills behave as intended, including across real
  sequential runs.
- `research/` — the pre-implementation competitive/differentiation research.

## Usage

Copy `adaptive-audit-plan/` to `.claude/skills/adaptive-audit-plan/` and
`adaptive-audit-execute/` to `.claude/skills/adaptive-audit-execute/` so
Claude Code discovers both. Ask something like "バグチェックして" to get a
plan first, or "このプランを実行して" / "実際に問題を探して" once you want it
carried out — `adaptive-audit-execute` will generate a plan itself first if
none exists yet, rather than auditing without a scoping decision.
