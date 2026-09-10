---
name: adaptive-audit
description: Produces a scoped, risk-aware Audit Plan for a codebase from a vague or specific natural-language request (e.g. "バグチェックして", "check this for bugs", "review before we ship", "パフォーマンス見て", "セキュリティ確認して"). Instead of running the same generic checklist every time, it inspects the actual project (stack, architecture signals, risk signals, existing tooling, recent changes) and decides which audit domains genuinely matter here — security, correctness, performance, reliability, architecture, data-integrity, concurrency, dependency-health, configuration/deployment, test-coverage, observability — at what depth, and explicitly which domains were NOT selected and why. It also keeps a local, cross-run history per project (outside the project itself) so a domain that keeps getting silently skipped across many differently-framed requests ("audit debt") gets surfaced and prioritized even when the current request doesn't mention it. Use this whenever someone asks for a code check/review/audit without pinning down exactly what to look at, before committing to a review approach, when the audit's scope itself needs to be justified rather than assumed, or when someone wants to know what hasn't been checked recently. This skill only produces the plan artifact — it does not run the audit, dispatch reviewer agents, or report findings. That is a separate, later step.
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

### 0. Check prior audit history for this project

This skill keeps a local, cross-run history *outside* the audited project (never
inside it — running this skill must never change the target repo's own git
status). This is what lets it track "audit debt" across different kinds of
audits over time, not just within one domain repeated on a schedule.

`scripts/receipts.py` lives next to this file (if this file is at
`/path/to/adaptive-audit/SKILL.md`, the script is at
`/path/to/adaptive-audit/scripts/receipts.py`). Run, with the project's root path:

```
python3 <skill-dir>/scripts/receipts.py debt --project-root <project-root>
```

This prints, per domain that has ever appeared in a past plan for this project:
how many times it was selected vs. excluded, the deepest it has ever been
audited, and how many runs it's been since that domain was last audited at
Deep depth. A domain with a high `runs_since_last_deep` (or that has *never*
been selected across many runs) has accumulated **audit debt** — it keeps
getting deprioritized run after run, regardless of what each individual
request happened to ask about. That is a real risk signal on its own, separate
from anything found in step 2, and step 3 must factor it in.

If this returns `"total_runs": 0` (or the command errors because no history
exists yet), say so plainly in the output and proceed — this is expected on a
project's first run, not a failure.

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
each. Score every domain using four inputs together:

1. **Explicit request signal** — did the person name this domain, or words close to it?
2. **Project signal strength** — how many/how strong are the matching signals from
   step 2?
3. **Blast radius** — domains touching auth, payments, PII, or money movement get a
   floor bump even without an explicit request, because the cost of skipping them is
   asymmetric. Don't let a purely performance-framed request silently drop a domain
   like this — surface it explicitly instead (see step 4).
4. **Accumulated audit debt** (from step 0) — a domain with a high
   `runs_since_last_deep`, or that has repeatedly scored just under the bar and been
   excluded run after run, gets a bump the same way a blast-radius domain does. A
   request being framed around something else this time is not a reason to let a
   long-neglected domain go another run untouched — that is exactly the gap this
   history exists to close.

Keep the taxonomy fixed across runs (don't invent new domain names ad hoc) — that's
what makes the debt calculation in step 0 possible at all; a domain that changes
names between runs looks like it was never audited.

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

### 5. Have the plan itself attacked before trusting it

Every other verification pattern in this space (and in `adaptive-audit-execute`)
checks *findings* — whether a reported bug is real. Almost nothing checks
whether the *plan* itself is any good, which means a confidently-written plan
that missed something obvious would sail through unchallenged. Close that gap
here, on every run, not just when something feels uncertain.

Dispatch a fresh, isolated critic subagent (via whatever subagent-spawning
capability this session has — the Task tool in Claude Code CLI, or the
equivalent here). Give it only: the raw project signals from step 2 and the
domain selection table from step 4 (selected + excluded, with depths and
reasoning) — not your own narrative justification for why the plan is good, and
not the original request. Ask it to argue against the plan: which selected
domain's depth looks mismatched to the signals actually cited for it (over- or
under-assigned)? Which excluded domain's stated reason doesn't actually hold up
against the signals listed? Is there a signal in step 2 that doesn't map to
*any* domain in the table at all?

Take the critic's output seriously, not performatively:
- A concrete, well-founded objection → revise the plan (change a depth, move a
  domain from excluded to selected, or vice versa) before writing the final
  output. Don't just append the objection as a footnote next to an unchanged
  decision.
- An objection that doesn't hold up on its own re-examination → keep the
  original decision, but record why the objection was rejected. Silently
  ignoring a raised objection is exactly the failure mode this step exists to
  catch — for the plan itself, not just for findings later.
- No objections raised → say so plainly; it's a real (if less interesting)
  outcome, not something to omit.

Record the outcome of this step in the "計画の自己検証" output section either
way.

### 6. Output the plan

Use the exact structure in "Output format" below. Write the prose sections in the
same language the person used in their request; keep the JSON block's keys in
English regardless (it's for machines, not for reading). Do not proceed to run any
audit, search for actual bugs, or produce findings — stop once the plan is written.

### 7. Record this run for next time

Write the JSON block from your output to a temp file and run:

```
python3 <skill-dir>/scripts/receipts.py write --project-root <project-root> <temp-file>
```

This is what makes step 0 possible on the *next* run against this project. List
every domain your `domains` array considered — selected **and** excluded — not
only the ones that made it into the plan; a domain that never appears in any
receipt looks indistinguishable from a domain nobody ever thought to check, which
would make the debt calculation meaningless. Do this even on a project's first run
(with no prior history to read) — that's how the second run gets history to read.

## Output format

ALWAYS use this exact structure (translate the prose headings to the request's
language; keep the JSON block's keys as-is):

````
# Audit Plan

## 過去の監査履歴
(what step 0 found: total prior runs, and any domain with notable accumulated
 debt — high runs_since_last_deep, or repeatedly excluded. If total_runs is 0,
 say this is the first recorded run for this project.)

## リクエストの解釈
(what was explicitly asked, what scope/depth was implied, what was left open)

## プロジェクトから検出したシグナル
(concrete signals found in step 2 — cite actual files/patterns, not assumptions.
 Note any signal you could not check.)

## 選定した監査観点
(table or list: domain | depth (Quick/Standard/Deep) | why — cite the specific
 signal(s) that drove the score, including debt from step 0 where it applied,
 not just the domain name)

## 見送った観点
(domain | why not selected this run — even if project signals existed)

## 計画の自己検証
(step 5's outcome: what the isolated critic objected to, if anything; for each
 objection, whether the plan was revised because of it or the objection was
 examined and rejected, and why. If no objections were raised, say so plainly
 rather than omitting this section.)

## 推奨する実行順序
(short list — which domain to actually audit first and why, e.g. highest blast
 radius or highest debt first, or the one the person actually asked about first)

## plan_record (JSON)
```json
{
  "schema_version": "1.0",
  "request": "<the original request, verbatim>",
  "domains": [
    {
      "domain_id": "<one id from references/audit-domains.md, e.g. \"security\">",
      "selected": true,
      "depth": "quick | standard | deep",
      "reasoning": "<short, same substance as the table above>",
      "evidence": ["<file:line or short pattern citation>", "..."]
    }
  ]
}
```
````

For an excluded domain in `plan_record`, set `"selected": false` and `"depth":
null`, but still fill in `reasoning` — that's the field step 0's debt calculation
and the "見送った観点" section both read.

## References

- `references/audit-domains.md` — the fixed domain taxonomy, detection signals per
  domain, and what each depth tier means. Read this during step 3, not before —
  it's reference material, not something to memorize up front.
- `scripts/receipts.py` — reads and writes this project's audit history (used in
  steps 0 and 6). Stdlib-only Python; run with `python3`, no install needed. Run
  `python3 <skill-dir>/scripts/receipts.py --help` if the exact flags aren't clear
  from steps 0/6 above.
