# adaptive-audit

Two Claude Code Skills, meant to be installed together. **`adaptive-audit-execute`
is the default for a plain request like "バグチェックして" or "check this for
bugs"** — a single natural-language request producing a real, complete audit
with no required follow-up question is the founding goal of this project, so a
vague first ask should not stop at a plan waiting for a second command.

- **`adaptive-audit-execute`** — given that kind of request, first generates a
  scoped, risk-aware **Audit Plan** (by running `adaptive-audit-plan`'s own
  process: inspecting the actual project and deciding which audit domains
  genuinely matter here — security, correctness, performance, reliability,
  architecture, data-integrity, concurrency, dependency-health,
  configuration/deployment, test-coverage, observability — at what depth, and
  which were *not* selected and why), then in the same response actually
  carries it out: an isolated Hunt pass per selected domain, then a separate
  isolated Verify pass that independently checks each candidate against the
  source before it's reported (CONFIRMED / PLAUSIBLE / REJECTED). Real
  findings, not just a plan.
- **`adaptive-audit-plan`** — the scoping half on its own, for when someone
  explicitly wants only that: "何を確認すべきか教えて(まだ実行しないで)",
  "計画だけ欲しい", or when they want to see/update the accumulated **audit
  debt** picture directly (`scripts/receipts.py report` renders it as a
  human-readable table, `export-csv` as CSV for Excel/Sheets — ask Claude to
  render a PDF from either when you need one to actually hand to someone,
  rather than that being a built-in, dependency-adding feature of the script
  itself). It also remembers, per project, which domains keep getting skipped
  across differently-framed requests over time, and surfaces that accumulated
  debt even when the current request doesn't mention it. Before finalizing,
  an isolated critic subagent argues against the plan itself — mismatched
  depth, an exclusion whose stated reason doesn't hold up, a signal that maps
  to no domain — closing a gap nothing else in the competitive research does:
  verifying the *plan*, not only the findings. `adaptive-audit-execute` runs
  this exact process as its own first step when it needs a plan.

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

A fifth idea — extracting a project's implied invariants ("a task's owner must
match the caller") and checking code against them directly, rather than only
scanning by domain — has now been validated across two independent trials
(a synthetic fixture, then a real ~10,895-line SaaS project), including one
case of independently rediscovering a real project's most severe confirmed
finding via a completely different reasoning path, and one case of finding a
real issue the domain-based pipeline had missed
(`adaptive-audit-execute/references/invariant-extraction.md`). It's still
**opt-in, not part of the default pipeline** — this was the highest-risk,
least-proven idea in the original research, and two successful trials (both
still scoped to auth/access-control-shaped invariants) is real evidence, not
yet enough to make it a default step for every run or every domain.

For a project that's already been fully audited once and only changed a
little since, `adaptive-audit-plan` (step 0.5) can offer a cheaper **diff-only
re-audit**, scoped to what actually changed (plus its direct blast radius)
instead of the whole project — but only when the change is clearly small
(≤15% of tracked files and ≤20 files), and it **asks rather than decides**:
it shows which domains have real accumulated debt a diff-only pass wouldn't
touch, then lets the person choose between diff-only and full. Diff-scoped
runs are tracked separately in `receipts.py`'s debt calculation
(`diff_checks_since_last_full`) so they're visible without being mistaken
for actually re-verifying the whole domain. Before any of this, step 0.4
runs `git fetch` (never `git pull` — this skill never writes to the audited
project's tracked files) and warns plainly, asking before proceeding, if the
local checkout is behind its remote — auditing (or diff-sizing against)
stale code silently is worse than admitting the checkout isn't current.

`adaptive-audit-execute` otherwise never writes to the audited project, with
one explicit opt-in: if the request explicitly asks for the findings report
to be saved into the project itself, it writes the same report to a file
under `docs/audit-reports/` (never `git add`/`git commit`s it — that stays
the person's own decision) — but only when explicitly asked, never inferred
from anything about the project (this skill has no reliable way to verify
who owns a repo, so ownership is never the trigger). If the report being
saved contains an unpatched security finding, it says so plainly in the
chat response before the person decides whether to commit: committing it
makes that detail part of the repository's git history permanently, even
after the underlying issue is fixed.

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
- `tests/` — automated pytest regression tests for `scripts/receipts.py`
  (run in CI via `.github/workflows/test.yml`). This is the one part of the
  project that's pure, deterministic logic rather than LLM output, so it's
  the one part an automated test suite can actually protect — `SKILL.md`
  behavior itself is still checked by hand-run evals in `evals/`, not CI.
- `VERSION` / `CHANGELOG.md` — version bookkeeping. Bumping `VERSION` on
  `main` makes `.github/workflows/release.yml` tag it and create a GitHub
  Release with auto-generated notes. This is also the version the
  `.claude-plugin/marketplace.json` plugin entry must be kept in sync with
  (enforced by `tests/test_versioning.py`) — see the "Install as a plugin"
  section below for what that's actually for.
- `.claude-plugin/marketplace.json` — makes this repo self-hostable as a
  single-plugin Claude Code marketplace, so an installed copy can actually
  be updated with a command instead of a manual re-copy. See "Install as a
  plugin" below.

## Usage

Two ways to install these skills — same skills, same behavior either way,
different update story:

**Plain copy** (no update mechanism — you re-copy by hand whenever you want
the latest): copy `adaptive-audit-plan/` to `.claude/skills/adaptive-audit-plan/`
and `adaptive-audit-execute/` to `.claude/skills/adaptive-audit-execute/`.

**As a plugin** (recommended if you want to actually pick up updates):
```
/plugin marketplace add kajisho5/adaptive-audit
/plugin install adaptive-audit@adaptive-audit
```
Later, to pull in whatever's newest on `main`:
```
/plugin marketplace update adaptive-audit
```
This is a personal/third-party marketplace (not an official Anthropic one),
so Claude Code's automatic background auto-update is **off by default** for
it — `/plugin marketplace update` above is the manual pull. To make it
actually automatic with no command needed, enable it yourself per-marketplace:
`/plugin` → Marketplaces → `adaptive-audit` → Enable auto-update. Either way,
skill auto-invocation (just saying "バグチェックして", no slash command) works
identically for a plugin-installed skill as for a manually copied one — the
`/adaptive-audit:...` slash-command form this adds is an alternative, not a
requirement.

Either way, just ask "バグチェックして" — that produces a plan and then
actually runs it in one go, without needing a second command. Ask for
"計画だけ欲しい" / "何を確認すべきか教えて" instead if you only want the
scoping decision without it being carried out yet.

## Cost

**Running this consumes your own Claude Code usage/API budget — whoever's
session runs the skill pays for that session's tokens, nobody else's.** There
is no shared backend and no mechanism for cost to land on anyone but the
person who typed the request. If you install this and run a Deep-depth audit,
that cost is yours; if someone else installs it from wherever you share it
and runs their own audit, that cost is theirs.

That cost is real and not small once you're past a Quick check. Measured
against real, unfamiliar third-party projects (not toy fixtures), a full
multi-domain audit at Standard/Deep depth has run:

| Language / shape | Size | Domains | Tokens |
|---|---|---|---|
| Python CLI tool | ~8,300 lines | 7 | ~1.7M |
| C/C++ network-facing library | ~20,600 lines | 7 | ~1.53M |
| TypeScript/Node web app | ~10,900 lines | 6 | ~1.05M |

(Project names withheld deliberately — see `evals/validation-notes.md` for
why some real-world findings from these runs are redacted there too.)

A Quick-only pass, or a plan-only request ("計画だけ欲しい"), costs a small
fraction of this — the depth you ask for (or that the plan assigns) is what
drives cost, not project size alone (a large but structurally repetitive
codebase can cost less than a smaller, denser one — see
`evals/validation-notes.md` for the full breakdown). If cost matters more
than thoroughness for a given ask, say so explicitly ("さっと見て" / "軽く
チェックして") — the plan step reads that as a depth signal.
