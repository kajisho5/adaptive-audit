---
name: adaptive-audit
description: Produces a scoped, risk-aware Audit Plan for a codebase from a vague or specific natural-language request (e.g. "バグチェックして", "check this for bugs", "review before we ship", "パフォーマンス見て", "セキュリティ確認して"). Instead of running the same generic checklist every time, it inspects the actual project (stack, architecture signals, risk signals, existing tooling, recent changes) and decides which audit domains genuinely matter here — security, correctness, performance, reliability, architecture, data-integrity, concurrency, dependency-health, configuration/deployment, test-coverage, observability — at what depth, and explicitly which domains were NOT selected and why. Use this whenever someone asks for a code check/review/audit without pinning down exactly what to look at, before committing to a review approach, or when the audit's scope itself needs to be justified rather than assumed. This skill only produces the plan artifact — it does not run the audit, dispatch reviewer agents, or report findings. That is a separate, later step.
---

# Adaptive Audit — Audit Plan Generator

## Why this exists

Most "review my code" tools run the same fixed checklist (usually security-only, or a
generic style/lint pass) no matter what the project actually is or what the person
actually asked. That wastes effort on domains that don't matter for this project, and
silently skips domains that do — with no record of the decision.

This skill's only job is to decide **what should be audited and why**, before any
audit actually runs. Treat the request as a starting signal, not the whole picture:
a project's actual code is often a better guide to what needs checking than the
words someone used to ask for it. Someone who says "バグチェックして" on a payment
webhook handler needs a different plan than someone who says the same thing about a
single-user CLI script — even though the request text is identical.

The output is always a plan, never findings. Don't audit anything yet, and don't
launch reviewer subagents — that's intentionally out of scope for this skill.

## Process

### 1. Interpret the request

Note, without over-fitting to exact wording:
- Any audit domain(s) explicitly named (security, perf, etc. — in any language)
- Any explicit scope (whole project vs. a diff/path/feature)
- Any explicit depth/urgency cue ("さっと見て" vs "徹底的に" vs "リリース前")

Treat this as a hint, not a ceiling. A request that only names one domain doesn't mean
other domains are off-limits — see step 4.

### 2. Inspect the actual project

Spend real effort here — this is what makes the plan adaptive instead of generic.
Gather concrete signals, don't guess from the project's name or a README's marketing
copy:

- **Stack**: manifest files (`package.json`, `requirements.txt`, `go.mod`, `Cargo.toml`,
  `pom.xml`, etc.), framework hints, language mix.
- **Architecture**: is there a network-facing server, a CLI, a library, a background
  worker/queue consumer, a database layer, a frontend? Grep for obvious markers
  (route/handler definitions, DB clients, message-queue clients).
- **Risk signals**: authentication/session code, payment or billing code, PII-shaped
  data (emails, addresses, government IDs), file uploads, deserialization,
  subprocess/`exec`/`eval` calls, raw SQL string building, use of secrets/env vars.
- **Concurrency signals**: goroutines/threads/async workers, shared mutable state,
  locks, queues.
- **Existing tooling**: CI config, linter/formatter config, test directories and
  their apparent coverage, dependency lockfiles and their freshness.
- **Recent activity**: `git log`/`git diff` against the base branch, if this is a
  repo with history — recently touched files deserve weight regardless of domain.

If a signal can't be checked (no git history, no manifest, sandboxed environment),
say so in the output rather than silently assuming it's absent.

### 3. Score each candidate audit domain

Read `references/audit-domains.md` now — it defines the fixed taxonomy of domains,
what signals make each one relevant, and what "Quick / Standard / Deep" means for
each. Score every domain using three inputs together:

1. **Explicit request signal** — did the person name this domain, or words close to it?
2. **Project signal strength** — how many/how strong are the matching signals from
   step 2?
3. **Blast radius** — domains touching auth, payments, PII, or money movement get a
   floor bump even without an explicit request, because the cost of skipping them is
   asymmetric. Don't let a purely performance-framed request silently drop a domain
   like this — surface it explicitly instead (see step 4).

Keep the taxonomy fixed across runs (don't invent new domain names ad hoc) — that's
what will let audit history/coverage be compared across different runs later.

### 4. Select domains and assign depth

- Select domains whose combined score clears a "worth mentioning" bar — this will
  usually be more than just the one domain the person explicitly named, unless the
  project genuinely has no other risk signals.
- Depth is per-domain, not uniform: a project can warrant Deep on security and Quick
  on performance in the same run.
- For every domain that scored high on project signals or blast radius but is **not**
  selected as a full audit target, list it under "見送った観点" with the concrete
  reason — a missing manifest file, no matching code pattern found, explicitly out of
  scope per the request, etc. Never omit a high-risk domain from the plan silently;
  if you're excluding it, say so and say why.
- For every domain that scored low across the board, it's fine to omit it from the
  output entirely — don't pad the plan with a long list of irrelevant domains.

### 5. Output the plan

Use the exact structure in "Output format" below. Write the plan in the same
language the person used in their request. Do not proceed to run any audit, search
for actual bugs, or produce findings — stop once the plan is written and hand it
back for confirmation or for the next phase to consume.

## Output format

ALWAYS use this exact structure (translate headings to the request's language,
keep the sections in this order):

```
# Audit Plan

## リクエストの解釈
(what was explicitly asked, what scope/depth was implied, what was left open)

## プロジェクトから検出したシグナル
(concrete signals found in step 2 — cite actual files/patterns, not assumptions.
 Note any signal you could not check.)

## 選定した監査観点
(table or list: domain | depth (Quick/Standard/Deep) | why — cite the specific
 signal(s) that drove the score, not just the domain name)

## 見送った観点
(domain | why not selected this run — even if project signals existed)

## 推奨する実行順序
(short list — which domain to actually audit first and why, e.g. highest blast
 radius first, or the one the person actually asked about first)
```

## References

- `references/audit-domains.md` — the fixed domain taxonomy, detection signals per
  domain, and what each depth tier means. Read this during step 3, not before —
  it's reference material, not something to memorize up front.
