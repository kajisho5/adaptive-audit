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
Claude Code discovers both. Just ask "バグチェックして" — that produces a plan
and then actually runs it in one go, without needing a second command. Ask for
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

| Project | Size | Domains | Tokens |
|---|---|---|---|
| `ffmpeg-skill` | ~8,300 lines | 7 | ~1.7M |
| `obs-studio` (`plugins/obs-outputs/`) | ~20,571 lines | 7 | ~1.53M |
| `open-saas` (`template/app/`) | ~10,895 lines | 6 | ~1.05M |

A Quick-only pass, or a plan-only request ("計画だけ欲しい"), costs a small
fraction of this — the depth you ask for (or that the plan assigns) is what
drives cost, not project size alone (a large but structurally repetitive
codebase can cost less than a smaller, denser one — see
`evals/validation-notes.md` for the full breakdown). If cost matters more
than thoroughness for a given ask, say so explicitly ("さっと見て" / "軽く
チェックして") — the plan step reads that as a depth signal.
