# adaptive-audit

> Status: **provisional**. Repository/skill name is a working name, not final —
> see `research/adaptive-audit-competitive-research.md` for why.

A Claude Code Skill that, given a natural-language request like "バグチェックして"
or "check this for bugs", inspects the actual target project and produces a
scoped, risk-aware **Audit Plan** — which audit domains actually matter here
(security, correctness, performance, reliability, architecture, data-integrity,
concurrency, dependency-health, configuration/deployment, test-coverage,
observability), at what depth, and explicitly which domains were *not* selected
and why.

This is a narrower MVP of a larger "Adaptive Audit Engine" concept. Before
building the full pipeline, a competitive investigation found that most of the
individual pieces (multi-agent review, evidence-based findings, self-verification)
already exist in well-established OSS (notably `cloudflare/security-audit-skill`
and `dinosn/raptor-loop-hunt`), so this repo currently only implements the two
confirmed white-space pieces, starting with the first:

1. **Domain-agnostic adaptive audit-plan generation** (this repo, MVP validated —
   see `evals/validation-notes.md`)
2. Cross-audit-type persistent coverage/audit-debt tracking (not yet built)

See `research/adaptive-audit-competitive-research.md` for the full competitive
analysis, feature matrix, and naming investigation behind these decisions.

## What's here

- `SKILL.md` + `references/audit-domains.md` — the skill itself. It only produces
  an Audit Plan; it does not run the audit, dispatch reviewer agents, or report
  findings.
- `evals/` — synthetic fixture projects, test prompts, and validation notes used to
  check the skill actually scopes adaptively instead of just following a fixed
  checklist.
- `research/` — the pre-implementation competitive/differentiation research.

## Usage

Copy (or symlink) this skill into a project's `.claude/skills/adaptive-audit/`
directory so Claude Code discovers it, then ask something like "バグチェックして"
or "review this before we ship" — Claude will produce an Audit Plan before doing
any actual review.
