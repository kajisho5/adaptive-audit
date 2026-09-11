---
name: adaptive-audit-execute
description: THE DEFAULT SKILL for any "check/review/audit this code" request, including a first, vague, unqualified one like "バグチェックして", "check this for bugs", "review this before we ship", "make sure this is solid" — with no other signal, this is the skill to use, not adaptive-audit-plan alone. Produces a scoped plan first (by following adaptive-audit-plan's process — inspecting the actual project and deciding which domains/depths genuinely matter, exactly as adaptive-audit-plan would on its own) and then, in the same response, actually carries it out: an isolated Hunt pass per selected domain, then a separate isolated Verify pass that independently checks each candidate against the source before it's reported (CONFIRMED/PLAUSIBLE/REJECTED) — real findings, not just a plan. A natural-language request producing a real, complete audit end to end, with no required follow-up question, is the entire point of this project; use adaptive-audit-plan by itself only when the person explicitly wants scoping without execution ("何を確認すべきか教えて", "計画だけ欲しい", "まだ実行しないで", "先に方針を確認したい", "what should we look at, don't actually check yet") — that is the exception this skill is not for, not the other way around. Never audits the target project's own files — reads only, and any reproduction/PoC work happens outside the project directory. Respects an explicit read-only/dry-run request (skips writing the execution result; the audit itself still runs and still reports real findings) rather than treating "don't touch anything" as a reason to decline the whole audit.
---

# Adaptive Audit — Plan Executor

## Why this exists, and why it's a separate skill from adaptive-audit-plan

adaptive-audit-plan deliberately only decides *what* to audit — it never looks for
actual bugs. That separation matters: deciding scope and finding issues are
different kinds of work, and conflating them is how you get a tool that either
skips the scoping step entirely (generic checklist, every time) or never actually
finds anything (all scope, no substance). This skill is the second half: given a
plan, go find out whether the things it flagged as worth checking actually have
problems.

That separation is an internal implementation detail, not something the person
asking should have to know about or manage themselves. The founding goal of this
whole project is that a single natural-language request — "バグチェックして" and
nothing else — produces a real, complete audit, the same way a human senior
engineer doesn't ask "should I first tell you my review plan and wait for your
go-ahead?" before actually reviewing something asked of them plainly. This skill
is what makes that true: it runs step 0 below to get (or generate) a plan, then
keeps going into Hunt/Verify in the same turn. Splitting that into two skills a
person has to explicitly chain themselves ("get me a plan" ... "now run it")
would recreate exactly the two-step, configure-then-run friction this project
set out to remove — so don't treat "no explicit execution signal in the request"
as a reason to stop after planning. Stopping after a plan is the deliberate,
narrower behavior of using adaptive-audit-plan directly, reserved for when
someone actually asks for only that.

The mechanism here — an isolated Hunter pass, then a separate isolated Skeptic/
Verify pass that doesn't inherit the Hunter's framing — is not novel; it is the
same shape used by `cloudflare/security-audit-skill` and `danpeg/bug-hunt`, among
others, and it exists here in its own right rather than as a dependency on either
of those because both are scoped to security/vulnerability hunting specifically.
Re-implementing the general pattern (not their prompts) is deliberate, not
invented-here syndrome — see the competitive research in this project's
`research/` directory for why building a domain-agnostic version of this pattern
was judged worth doing rather than reused wholesale.

## Process

### 0. Get a plan to execute

Check whether the request carries a read-only / no-side-effects / dry-run
constraint (see adaptive-audit-plan's step 1 for the same signal — same
wording patterns apply here). If so, this whole run is in **dry-run mode**:
carry that forward into every step below that writes anything. Dry-run changes
*what gets written*, never *what gets investigated* — the hunt and verification
work happen exactly as normal and still produce real findings; only the
receipt-writing steps are affected. A request to not touch anything is a reason
to skip *writes*, not a reason to decline the audit itself.

Look for a `plan_record` (the JSON block adaptive-audit-plan produces) and its
receipt id (the path `receipts.py write` printed, or the `id` field inside the
written receipt file) already available in this conversation. If neither exists
yet, produce one now by following `../adaptive-audit-plan/SKILL.md`'s process in
full — including its own step 7 (writing the plan receipt), unless this run is
in dry-run mode, in which case that nested run skips its step 7 the same way a
standalone adaptive-audit-plan invocation would. Never audit without going
through the scoping step, even under time pressure, and even in dry-run mode:
skipping *writes* is not the same thing as skipping the plan.

Once you have a plan, only its **selected** domains (`selected: true`) get
executed, in the plan's stated execution order. Excluded domains stay excluded —
this skill carries out a decision, it doesn't second-guess it. If the user wants
a previously-excluded domain audited too, that's a new planning input, not
something for this skill to decide on its own.

### 1. Hunt (per domain, isolated)

For each selected domain, in order, dispatch a **fresh subagent with no visibility
into any other domain's hunt or this skill's own reasoning** — only: the domain
id, the plan's stated reasoning/evidence pointers for it, the project root, and
that domain's Quick/Standard/Deep definition from
`references/audit-domains.md` (same file adaptive-audit-plan uses — read it now
for the domains you're about to hunt, not before). Isolation matters here for the
same reason it matters in every adversarial-review design that's already proven
this out: a hunter that already knows what the plan expected to find anchors on
confirming it, rather than actually looking.

**If no mechanism for real subagent isolation exists in this environment** (no
Task tool available, or spawning a subagent/session is blocked) — this can happen
in a nested or restricted execution context — do not silently skip isolation and
report as if it happened. Instead: say so plainly in the output's 実行サマリー
section, and still perform steps 1 and 2 as two clearly separated reasoning
passes within this session — read only that domain's lens in step 1, and in
step 2 deliberately discard whatever confidence you formed in step 1 and
re-derive each candidate's status from the source alone, actively trying to
disprove it rather than confirm it. This is a real degradation (it can't rule
out the same reasoning anchoring both passes the way physical isolation does),
not a cosmetic one — disclosing it is what lets whoever reads the result decide
whether that's good enough for their purposes.

Two concrete techniques make this fallback less prone to anchoring than just
"trying to be skeptical," even though neither fully replaces real isolation:

1. **Strip the candidate down before re-reading it.** Write step 1's candidates
   to a temp file (outside the project) as the bare JSON shape only — title,
   file, lines, severity, description, failure_scenario — with none of the
   hunt's surrounding narrative, confidence language, or "I'm fairly sure
   this is real because..." reasoning. When step 2 starts, treat that stripped
   JSON as if it arrived from someone else: re-open the actual source at the
   cited lines and re-derive CONFIRMED/PLAUSIBLE/REJECTED from scratch, rather
   than re-reading your own step-1 prose. This mirrors what a truly isolated
   Verify subagent would receive (SKILL.md step 2 gives it the claim, not the
   hunter's reasoning) — the fallback can't replicate the separate context
   window, but it can replicate what information crosses the boundary.
2. **Batch step 1 across every domain before starting step 2 on any of them**,
   rather than doing Hunt-then-Verify domain by domain. More turns and more
   unrelated domains' reasoning between forming a candidate and re-checking it
   makes it modestly harder for the exact justification to still be live in
   working context — not a substitute for isolation, but cheap and free to do.

State in the 実行サマリー not just *that* the fallback was used, but *which*
of these mitigations were actually applied — "same-session fallback, no
stripping, sequential per domain" is a materially weaker disclosure than
"same-session fallback with candidate-stripping and full Hunt-before-Verify
batching," and the reader deciding whether the result is good enough for them
needs to know which one they got.

Depth controls how far the hunt goes, using each domain's own Quick/Standard/Deep
definition in the reference file — a Quick security pass is a pattern scan, a
Deep one attempts safe reproduction; don't apply one uniform depth policy across
domains. Whatever depth calls for, this skill reads the target project but never
writes to it: a Deep-depth reproduction attempt (a sandboxed server instance, a
stress-test script, a PoC) runs from outside the project directory — write any
temp files it needs under `/tmp` or similar, never inside the project being
audited. This holds regardless of dry-run mode; dry-run only changes whether
this skill's own receipt/result get written, not whether the target project's
own files are ever touched (they never are, either way).

**Staged escalation for `depth_confidence: "provisional"` domains.** A domain
the plan assigned Standard or Deep with `depth_confidence: "high"` (or with no
`depth_confidence` field at all, for a plan produced before this field existed)
goes straight to that depth as a single Hunt pass — no change from before. But
a domain assigned Standard or Deep with `depth_confidence: "provisional"` (a
generic-baseline call, not a specific strong signal) gets a cheaper two-step
treatment instead, since a full Standard/Deep Hunt subagent is real, non-trivial
cost that a provisional call hasn't clearly earned yet:

1. Dispatch a Quick-depth Hunt pass for that domain first (same isolation rules
   as any other Hunt pass).
2. If that Quick pass returns **any** candidate (regardless of severity), escalate:
   dispatch a second Hunt pass at the plan's originally assigned depth (Standard
   or Deep) for the same domain — but this time give the hunter the Quick pass's
   own candidates as known starting points to build on and go deeper from, plus
   the instruction to also look beyond them. This keeps the Quick pass's work from
   being wasted when escalation happens, rather than discarding it and starting
   the deeper pass from nothing.
3. If the Quick pass returns **zero** candidates, stop at Quick for that domain.
   Do not silently treat this as equivalent to a clean Standard/Deep result: it
   means only a Quick-depth pass actually ran, and step 3 below (and the receipt
   in step 5) must record the depth that was *actually executed* (`quick`), not
   the depth the plan originally called for. This is the same "count what
   actually happened" principle this skill already applies to a cut-short Deep
   pass — a provisional domain that stopped at Quick has real, disclosed audit
   debt remaining on it, even though nothing went wrong in this run.

This only ever reduces cost relative to always running the full planned depth —
it never runs *more* Hunt passes than a `high`-confidence domain of the same
planned depth would, since a `high`-confidence domain never gets a Quick pass
at all. The tradeoff is real, not free: a `provisional` domain that stops at
Quick got less scrutiny this run than its plan originally called for, in
exchange for not spending a full Standard/Deep pass on a domain whose need for
that depth wasn't clearly established in the first place. State plainly in the
実行サマリー whenever this happened, and for which domains.

Instruct the hunter to output candidates in this shape, one per issue, and to
resist padding the list — a domain with nothing wrong should come back with an
empty candidate list, not manufactured minor nits:

```
{
  "domain_id": "<the domain being hunted>",
  "title": "<short, specific>",
  "file": "<path>",
  "lines": "<line or range>",
  "severity": "high | medium | low",
  "description": "<what the code does, and why it's a problem>",
  "failure_scenario": "<concrete input/state -> concrete bad outcome, not a vague risk statement>"
}
```

### 2. Verify (per candidate, isolated from the hunt)

For every candidate from step 1, dispatch a **separate fresh subagent** — one
that sees only the candidate's claim and the actual source, not the Hunter's
confidence or reasoning — to independently decide:

- **CONFIRMED**: can trace the exact mechanism end to end; the failure scenario
  is real and reproducible from the code as written.
- **PLAUSIBLE**: a genuine code smell or missing safeguard, but exploitability,
  reachability, or actual impact isn't confirmed from the code alone.
- **REJECTED**: not actually a problem — mitigated elsewhere, a misread of the
  code, or the failure scenario doesn't actually follow from it.

This step exists because a hunter under instructions to find things will find
things whether or not they're real — the same reasoning `cloudflare/
security-audit-skill`'s independent-verification phase and `danpeg/bug-hunt`'s
Skeptic role are built on. Drop every REJECTED candidate before reporting;
keep CONFIRMED and PLAUSIBLE, labeled as such — never silently upgrade a
PLAUSIBLE to sound confirmed just because it made it into the report.

**For `security`-domain candidates specifically, lead with static/manual source
tracing, not a rebuilt exploit harness.** Quote the exact code, trace the exact
call chain, and do the arithmetic/logic by hand first — this alone is usually
enough to reach CONFIRMED/PLAUSIBLE/REJECTED. Only reach for compiling and
running a dynamic PoC (an ASan harness, a crafted-input reproduction, etc.) if
static tracing genuinely can't settle the verdict, and treat it as a secondary,
optional confirmation rather than the primary method. This isn't just a cost
optimization: a real run against a memory-unsafe C/C++ codebase found that
leading a Verify prompt with "rebuild and run a harness" can get the subagent's
turn interrupted by this kind of environment's own automated cyber-content
safety filtering — a false-positive on legitimate, authorized defensive review,
not a finding about the work itself, but a real interruption all the same.
Static-first framing reaches the same conclusions without tripping it.
**If a security Verify pass is interrupted by this kind of filter anyway**,
do not resume or retry the same dynamic-harness approach — dispatch a fresh
Verify subagent for that candidate with an explicitly static/manual-tracing-
first instruction (as above) instead of picking the interrupted attempt back
up; this has reliably reached the same conclusion without re-tripping the
filter.

### 3. Check execution actually matched the plan

Before writing anything up, compare what got executed against what the plan
said would happen: did every selected domain get a hunt pass, at the depth the
plan specified? If a domain was skipped, cut short, or the hunt genuinely ran out
of budget/time before finishing a Deep pass, say so explicitly in the output — a
plan that promised Deep security and got Quick-equivalent effort is a shortfall
worth surfacing on its own, not something to paper over by reporting whatever was
found as if it were complete. This is what keeps the audit-debt history (step 5)
honest: a domain only counts as actually looked at if it actually was.

A `depth_confidence: "provisional"` domain that stopped at Quick under step 1's
staged-escalation rule is a different case from an unintended shortfall — it's
the mechanism working as designed, not something that went wrong — but it still
gets recorded as executed-at-Quick, not at the plan's originally stated depth,
for the same reason: the debt history has to reflect what actually happened.
Distinguish the two plainly in the output (an intentional staged stop vs. a
genuine shortfall) so a reader doesn't mistake one for the other.

### 4. Output the findings report

Use the exact structure in "Output format" below, in the same language as the
original request. Group by domain, in the plan's execution order. Within a
domain, CONFIRMED findings first, then PLAUSIBLE. State `overall_status` using
worst-wins: FAIL if any CONFIRMED finding is high or medium severity, WARN if
only low-severity CONFIRMED or any PLAUSIBLE findings exist, PASS if every
executed domain came back clean, UNKNOWN if nothing was actually executed (step
3 found a shortfall covering everything).

### 5. Record the outcome — unless step 0 found a dry-run constraint

**In dry-run mode, skip this step entirely** — no result JSON, no temp file, no
`write-result` call. State plainly in the 実行サマリー that this execution was
not recorded, so the next run's debt calculation won't show this domain as
verified even though it genuinely was this time. That's the same known,
disclosed tradeoff as adaptive-audit-plan's own dry-run mode, not a gap unique
to this skill.

Otherwise, write a result JSON (schema below) to a temp file (outside the
target project, as always) and run:

```
python3 <skill-dir>/scripts/receipts.py write-result --project-root <project-root> --plan-id <plan-receipt-id> <temp-file>
```

Include every domain that was *actually executed* (got a real hunt pass),
regardless of whether it came back clean — a clean result is still a verified
result and should count toward reducing that domain's audit debt. Do not include
a domain here if step 3 found its execution fell short of the plan (e.g. it was
skipped, or a Deep pass was really only completed to Quick depth) — the whole
point of this record is that `max_verified_depth_ever` in the debt calculation
reflects work that actually happened, not work that was merely attempted.

**Record each domain's `depth_executed`** — the depth that Hunt actually ran at
for that domain, not the plan's originally assigned depth. For almost every
domain these are the same value. They differ specifically for a
`depth_confidence: "provisional"` domain that stopped at Quick under step 1's
staged-escalation rule: its `depth_executed` is `"quick"`, even though the plan
said `"standard"` or `"deep"`. `receipts.py`'s debt calculation reads this field
(falling back to the plan's depth only for old result records that predate it)
— getting this field right is what keeps a staged-escalation stop from being
silently miscounted as full-depth verification.

## Output format

ALWAYS use this exact structure (translate headings to the request's language;
keep the JSON keys as-is):

````
# Audit Result

## 実行サマリー
(overall_status; which domains were executed at which depth vs. what the plan
 asked for; any shortfall from step 3, stated plainly; whether Hunt/Verify ran
 as truly isolated subagents or as the same-session fallback from step 1/2 —
 never leave this unstated; whether this run is in dry-run mode and, if so,
 that the result was not recorded — never leave that unstated either)

## <domain 1> の結果
(CONFIRMED findings first, then PLAUSIBLE — each with file:lines, severity,
 description, failure scenario. If none survived verification, say so plainly
 rather than omitting the section.)

## <domain 2> の結果
...

## result_record (JSON)
```json
{
  "domains": [
    {
      "domain_id": "<domain actually executed>",
      "depth_executed": "quick | standard | deep (the depth Hunt actually ran at -- see step 5)",
      "confirmed_findings": 0,
      "plausible_findings": 0,
      "rejected_findings": 0
    }
  ]
}
```
````

## References

- `references/audit-domains.md` — same fixed taxonomy and depth-tier definitions
  adaptive-audit-plan uses; read the entries for domains you're about to hunt.
- `scripts/receipts.py` — same history store adaptive-audit-plan writes to;
  `write-result` links this run's outcome back to the plan it executed. Run
  `python3 <skill-dir>/scripts/receipts.py --help` if a flag isn't clear from
  step 5 above.
