---
name: adaptive-audit-plan
description: Produces ONLY a scoped, risk-aware Audit Plan for a codebase — no actual bug-finding. Instead of running the same generic checklist every time, it inspects the actual project (stack, architecture signals, risk signals, existing tooling, recent changes) and decides which audit domains genuinely matter here — security, correctness, performance, reliability, architecture, data-integrity, concurrency, dependency-health, configuration/deployment, test-coverage, observability — at what depth, and explicitly which domains were NOT selected and why. It also keeps a local, cross-run history per project (outside the project itself) so a domain that keeps getting silently skipped across many differently-framed requests ("audit debt") gets surfaced and prioritized even when the current request doesn't mention it.

IMPORTANT — for a first, vague, unqualified request like "バグチェックして" or "check this for bugs" with no other signal, use `adaptive-audit-execute` instead, NOT this skill alone: that skill generates this exact plan as its own first step and then actually carries it out in the same response, which is what most people mean by that kind of request. Use this skill by itself only when the person explicitly wants scoping without execution — "何を確認すべきか教えて(まだ実行しないで)", "計画だけ欲しい", "先に方針を確認したい", "what should we look at, don't actually check yet", or when they want to see/update the accumulated audit-debt picture on its own. Respects an explicit read-only/dry-run request (no history gets recorded for that run, and it says so). This skill only produces the plan artifact — it does not run the audit, dispatch reviewer agents, or report findings.
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

### 0.4. Make sure the local checkout is actually current

Every downstream step — signal inspection, domain scoring, and especially
step 0.5's diff sizing just below — assumes the local working tree reflects
the code that actually matters right now. A local clone that's behind its
remote quietly breaks that assumption: the plan gets built against stale
code, and step 0.5's diff-mode decision could look at the wrong (too small,
or entirely wrong) set of changes without anyone noticing. Run this before
step 0.5, not after — there's no point sizing a diff against a HEAD that
might not be current yet.

If this is a git repository with a configured remote, run `git fetch` (not
`git pull`) and compare local `HEAD` against the corresponding remote-
tracking branch. `git fetch` never touches the working tree or any tracked
file, so it doesn't conflict with this skill never writing to the audited
project's own files. `git pull` would touch the working tree, so never run
it automatically here, even to "help."

**In dry-run mode, skip the `git fetch` call itself** — it does write inside
the project's own `.git/` directory (updated remote-tracking refs,
`FETCH_HEAD`), which is a real side effect even though it never touches a
tracked file, and dry-run mode's promise is no side effects on the target
repo at all. Instead, compare local `HEAD` against whatever remote-tracking
ref already happens to exist locally (which may itself be stale) and
disclose plainly that freshness could not be actively verified this run
because of the read-only constraint — the same honest tradeoff dry-run mode
already makes everywhere else in this skill.

- **Local HEAD matches or is ahead of the remote**: proceed normally, no
  need to mention this in the output.
- **Local HEAD is behind the remote**: say so plainly and prominently in the
  output (see "Output format"), stating how many commits behind. Ask the
  person whether to proceed against the current (stale) checkout anyway, or
  pull first and re-run — don't silently pick either. Auditing stale code
  and reporting it as if it were current is a worse failure mode than
  simply admitting the checkout is behind.
- **No remote configured, not a git repo, or the fetch fails** (offline,
  no network access, private remote unreachable from this environment):
  say so and proceed against the local checkout as-is — this is the same
  honest-disclosure-over-silent-assumption handling as any other signal in
  step 2 that can't be checked.

### 0.5. Check for a small-diff re-audit opportunity — and let the person decide, don't decide for them

Skip this step entirely if step 0 found no history (`total_runs: 0`), if this
project isn't a git repository, or if this run is already in dry-run mode.
Otherwise (step 0.4 has already run by this point):

1. From `list-results` (falling back to `list` if no execution results exist
   yet), find the most recent record whose `scope` is `"full"` or absent
   (legacy records with no `scope` field are full-scope by definition) **and**
   that has a `git_commit` field. If none exists, skip this step — there's
   nothing to diff against yet.
2. Run `git diff --shortstat <that commit>..HEAD -- .` (and `git ls-files | wc
   -l` for the project's total tracked file count) to measure how much has
   actually changed since that commit.
3. Only offer diff-mode when the change is **clearly small**: changed files
   are both ≤15% of the project's total tracked files **and** ≤20 files in
   absolute terms. If the diff is larger than that, don't ask — proceed
   straight to step 1 as a full-scope run, the same as always. This
   deliberately errs toward not bothering the person with a choice that isn't
   a real cost/thoroughness tradeoff yet.
4. If the diff qualifies, **ask the person directly** (via `AskUserQuestion`
   if available, otherwise as a plain question in the response, and wait for
   an answer before proceeding) rather than picking one silently. Show them
   what they need to actually decide, not just "small or large":
   - The base commit, its age, and the changed file/line count.
   - Which domains currently have real accumulated debt (STALE/UNAUDITED/
     PLANNED-ONLY per step 0's `report`) — a diff-only pass will **not**
     touch those, so choosing it means that debt keeps aging. Say this
     plainly; don't let the speed/cost upside hide this cost.
   - The two options: **diff-only** (fast, cheap, scoped to what actually
     changed) vs. **full** (re-examines everything, including domains with
     existing debt).
5. If they choose **diff-only**: this run's `scope` is `"diff"`. Scope step 2's
   project inspection, step 3-4's domain scoring, and (in
   `adaptive-audit-execute`) the actual Hunt passes to the changed files
   themselves plus their direct blast radius (grep for what imports/calls
   them elsewhere in the repo — don't re-read the whole project). Record
   `diff_base_commit` (the commit diffed against) and `diff_files` (the
   changed file list) in the `plan_record`, alongside `"scope": "diff"`.
6. If they choose **full**, or this step was skipped or didn't qualify: this
   run's `scope` is `"full"` (the default — always set it explicitly in the
   `plan_record` even when nothing about this step applied, since
   `adaptive-audit-execute`'s debt calculation needs every plan's scope to
   read reliably, not just diff-scoped ones).

Either way, record the current `git_commit` (`git rev-parse HEAD`, if this is
a git repo) in the `plan_record` — this is what makes the *next* run's step
0.5 possible. A project with no git history simply never qualifies for this
step; that's a known, accepted limitation, not something to work around.

### 1. Interpret the request

Note, without over-fitting to exact wording:
- Any audit domain(s) explicitly named (security, perf, etc. — in any language)
- Any explicit scope (whole project vs. a diff/path/feature)
- Any explicit depth/urgency cue ("さっと見て" vs "徹底的に" vs "リリース前")
- **Any read-only / no-side-effects constraint** ("読み取り専用で", "ファイルを一切
  変更・作成・削除しないで", "dry-run", "don't touch anything", "just look, don't
  write anything") — if present, this run is in **dry-run mode**: skip step 7
  (recording the receipt) entirely rather than either violating the constraint or
  quietly ignoring it. Say so plainly in the output (see "Output format"). A
  constraint like this is exactly the kind of thing that otherwise causes a
  reasonable-but-wrong outcome — silently skipping this whole skill instead of
  just skipping its one side-effecting step — so treat it as a normal mode to
  support, not an edge case to work around.

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

**For every domain assigned Standard or Deep, also record a `depth_confidence`:**
Standard/Deep execution is real cost (`adaptive-audit-execute` dispatches at least
one full-depth Hunt subagent per domain) — this field tells that skill whether it's
safe to spend that cost immediately or worth cost-gating first.

- **`high`**: the Standard/Deep assignment is grounded in a *specific* signal from
  step 2 or 3 — a concrete file/pattern citation, an explicit blast-radius category
  (auth/payment/PII/money movement), the person explicitly naming this domain, or a
  high accumulated-debt bump. Something a skeptic could point at and say "yes, that
  clearly warrants more than a Quick pass."
- **`provisional`**: the Standard/Deep assignment mainly comes from a domain's
  generic baseline reasoning (e.g. correctness's "any project" baseline, or
  test-coverage's "any project with a test directory" baseline) *without* a
  specific signal pointing at Standard/Deep depth *specifically* for this project —
  it's a reasonable default, not a confident call.

This is not a new scoring input — it doesn't change which domains get selected or
what depth they're assigned in step 3-4 above. It's a separate, honest label on
*why* that depth was assigned, and `adaptive-audit-execute` uses it to decide
whether to run that depth immediately or stage up to it (see that skill's step 1).
Domains assigned Quick, or excluded, don't need this field (leave it out or null).

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

### 7. Record this run for next time — unless step 1 found a dry-run constraint

**In dry-run mode, skip this step entirely.** Do not write to a temp file
outside the project either — the point of dry-run is no filesystem side effects
from this run, not just none *inside* the project. State plainly in the output
that this run was not recorded, and that debt tracking on the *next* run
against this project won't reflect it. This is a real, known cost of dry-run
mode, not a detail to gloss over: a project audited repeatedly in dry-run mode
will never show reduced debt for the domains it covered, because nothing was
ever written down. That's the honest tradeoff for guaranteeing no side effects,
not a bug in the mechanism.

Otherwise, write the JSON block from your output to a temp file (outside the
target project — e.g. under `/tmp`, never inside the project being audited,
dry-run or not) and run:

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
(if step 1 found a dry-run/read-only constraint, say so in one line right here,
 before any other section: this run will not be recorded, and why. If step 0.4
 found the local checkout behind its remote, say that here too, just as
 prominently — how many commits behind, and whether the person chose to
 proceed against the stale checkout or pull first and re-run)

## 過去の監査履歴
(what step 0 found: total prior runs, and any domain with notable accumulated
 debt — high runs_since_last_deep, or repeatedly excluded. If total_runs is 0,
 say this is the first recorded run for this project. Reading history is safe
 in dry-run mode too — only step 7's write is skipped, not step 0's read.)

## 差分監査の判断
(only include this section when step 0.5 actually ran and found a qualifying
 small diff: the base commit and how much changed, which domains have
 existing debt a diff-only pass wouldn't touch, which option was chosen and
 by whom (the person, via the question step 0.5 asked) — omit this section
 entirely, don't just say "N/A", when step 0.5 didn't apply)

## リクエストの解釈
(what was explicitly asked, what scope/depth was implied, what was left open)

## プロジェクトから検出したシグナル
(concrete signals found in step 2 — cite actual files/patterns, not assumptions.
 Note any signal you could not check.)

## 選定した監査観点
(table or list: domain | depth (Quick/Standard/Deep) | depth_confidence
 (high/provisional, only for Standard/Deep domains) | why — cite the specific
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
  "scope": "full | diff (see step 0.5 -- always set, default is \"full\")",
  "git_commit": "<git rev-parse HEAD, if this is a git repo -- omit otherwise>",
  "diff_base_commit": "<only when scope is \"diff\": the commit diffed against>",
  "diff_files": ["<only when scope is \"diff\": the changed files>"],
  "domains": [
    {
      "domain_id": "<one id from references/audit-domains.md, e.g. \"security\">",
      "selected": true,
      "depth": "quick | standard | deep",
      "depth_confidence": "high | provisional | null (only meaningful when depth is standard/deep)",
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
  steps 0 and 7). Stdlib-only Python; run with `python3`, no install needed. Run
  `python3 <skill-dir>/scripts/receipts.py --help` if the exact flags aren't clear
  from steps 0/7 above. Also has `report` (human-readable) and `export-csv`
  (for Excel/Sheets) — not part of this skill's own steps, but worth mentioning
  to someone who wants to see or share the accumulated debt picture directly,
  rather than only through a freshly generated plan.
