# Invariant Extraction (opt-in enhancement)

**Status: validated across four trials, but still opt-in — not part of the
default `adaptive-audit-execute` pipeline.** Do not invoke this
automatically during a normal run; use it when the user has explicitly asked
for invariant-based analysis, or when `security` is selected at Standard/Deep
depth and you judge the extra scrutiny worth the roughly-one-domain's-worth of
additional cost (see "Trial 2" below for real numbers). This is deliberately
kept out of `SKILL.md` step 1 as a *default* step rather than promoted to one
— see "Current standing" below for exactly what has and hasn't been shown.

**Public beta — third-party trial reports wanted.** Every trial so far was
run by this project's own author using this project's own verification
methodology, which is not independent evidence of anything — it's the same
source repeated four times. Before this could reasonably be promoted out of
opt-in status, it needs trial reports from people with no connection to this
project, on projects its author has never seen. If you try this on your own
project, please report back (positive or negative results both count) at
[issue #12](https://github.com/kajisho5/adaptive-audit/issues/12).

## What this is

Per the competitive research (`research/adaptive-audit-competitive-research.md`),
invariant extraction — inferring what must always be true about a system from
its own code structure, then checking whether the code actually upholds it —
was the single most novel and least-validated idea in the original concept.
Only one prior attempt was found anywhere in the ecosystem
(`dystopiaxyz/hound-audit-ai`), and it was unused (0 stars). This file documents
a small, real test of the technique, not a proven production feature.

## The technique

Given a project, without reading tests or external docs, extract 5-10
invariants purely from the code's own structure — field names, function names,
route names, whitelist/filter logic — each as a plain-English sentence, tagged
with what part of the code implies it and a confidence level. Then, separately,
check each invariant against the actual code and cite whether it holds or is
violated.

Output shape per invariant during extraction:
```json
{"invariant": "...", "implied_by": "...", "confidence": "high|medium|low"}
```

The two-pass structure (extract *before* checking) matters: it's what makes
the technique falsifiable rather than a rationalization exercise — extracting
invariants while already looking for violations would just reproduce whatever
the hunt already found, framed differently.

## Validation result (one run, `task-api` fixture)

Extracted 9 invariants with no prior knowledge of the fixture's seeded bugs.
Checking against the actual code: 6 violated, 2 held, 1 conditional/latent
(deployment-dependent). Two of the violated invariants — task ownership, and
the `status`/`claimed_by` pairing — independently converged on the exact same
two bugs `adaptive-audit-execute`'s domain-based Hunt found via a completely
different framing (top-down "what must hold" vs. bottom-up "what looks
wrong"). That convergence, from two different reasoning paths landing on the
same real bug, is a stronger signal than either path alone.

The run's own honesty check (asked explicitly, not just a "did it work"
report): of the 9 invariants, 6 were tightly grounded in unambiguous code
structure and cleanly checkable; the other 3 leaned more on generic
security-hygiene expectations than on anything the code's own design
specifically implied. That's a real limitation to keep in view — invariant
extraction on a small, single-purpose fixture is easier than on a large,
architecturally varied codebase where "what does this field name imply"
stops being an obvious question.

## Trial 2 (real project, `wasp-lang/open-saas`, security-adjacent scope)

Run against a real, ~10,895-line production-quality SaaS template — a
meaningfully different test than trial 1's small synthetic fixture — scoped to
auth/payment/file-upload/user/admin, the areas already known (from a prior,
independent, full domain-based `adaptive-audit-execute` run against this same
project — see `evals/validation-notes.md` iteration 11) to contain 4 confirmed
security findings among 18 total confirmed findings across 6 domains. The
extraction agent had **no knowledge of that prior run or any of its findings**.

Extracted 12 invariants. Checking against the code: 10 HELD, 1 VIOLATED, 1
CONDITIONAL. Both non-HELD classifications were independently re-verified by a
fresh adversarial Verify pass, exactly as a normal Hunt candidate would be:

- **The VIOLATED invariant independently rediscovered the single most severe
  finding from the prior domain-based run** (`getDownloadFileSignedURL` having
  no `context` parameter at all, no auth check, no ownership check) — via a
  completely different reasoning path (noticing every sibling operation shares
  a repeated ownership-scoping pattern, then finding the one file that breaks
  it, rather than domain-based Hunt's top-down "what could go wrong in this
  domain" framing). This is the second independent trial, on two very
  different codebases, showing the same convergence property trial 1 first
  demonstrated — no longer a one-off.
- **The CONDITIONAL invariant found something genuinely new**: the prior
  domain-based run's `security` domain never surfaced that
  `ensureStripeCustomer` looks up Stripe customers by email and silently
  reuses a pre-existing one, which can bind a new local user to a Stripe
  customer with unrelated billing history under some (narrow, mostly
  dev/deployment-hygiene) preconditions. Independently Verify'd as CONFIRMED —
  real, but honestly assessed by that Verify pass as low-to-medium severity
  given this app has no account-deletion feature that would make the
  realistic trigger easy to hit in production. This is the first concrete
  evidence of the technique's speculative "added value over domain-based
  hunting" actually happening, not just converging on what domain-based
  hunting would have found anyway.

**False-positive rate**: 2 of 2 non-HELD classifications confirmed real on
independent adversarial re-check (0 false positives this trial). Genuinely
better news than expected, but `n=2` is too small to treat as a rate rather
than an anecdote — this is progress on the "no false-positive-rate data" gap,
not closure of it.

**Cost**: ~120K tokens for the extract+check pass, ~70K tokens to
independently Verify the one new claim — **≈190K tokens total**. For
reference, the prior domain-based run's `security` domain alone (Hunt + Verify,
Deep depth, same project) cost ≈213K tokens. So this trial's invariant pass
cost *roughly the same as the existing security domain's own process*, while
independently reconfirming its top finding and adding one the domain-based
process had missed — a genuinely favorable cost/value comparison, not just "an
extra thing that also costs extra."

**Real limitation surfaced, not just a caveat**: scoping extraction to
security-adjacent code did not mean it produced security-adjacent invariants
comprehensively. The extraction agent read all three payment webhook
handlers in full (the exact code with the confirmed missing-idempotency bug
from the domain-based run's `data-integrity` domain) but never generated an
invariant along the lines of "processing the same webhook event twice must
not double-apply its effect" — it noticed the signature-verification pattern
repeated across the three files, but not the missing-idempotency pattern
also present in all three. The technique has a real "attention" bias toward
whatever structural pattern happens to catch it, not uniform coverage of
everything in the code it reads — this is a limitation worth designing
around (e.g., explicitly prompting for invariants about *effects of
repeated/duplicate input*, not just *authorization/ownership*), not just
disclosing.

## Trial 3 (same project, directed at duplicate-input/state-transition invariants)

Trial 2's attention-bias limitation — missing an idempotency invariant despite
reading the exact vulnerable webhook code — raised an obvious question: was
that a limitation of the technique itself, or just of an extraction prompt
aimed at authorization/ownership invariants specifically? Re-ran against the
same project's `payment/` subsystem, same no-prior-knowledge condition, but
this time the extraction prompt explicitly asked for invariants about
*effects of repeated/duplicate input, state transitions, and derived-value
consistency* rather than a generic prompt.

Result: **the redirected prompt found the missing-idempotency bug directly.**
Two of ten extracted invariants ("applying the same external event twice must
not double-apply its effect," "a derived incrementing value needs a mechanism
tying each increment to a unique source-event id") were checked as VIOLATED
with the exact same mechanism and severity the domain-based `data-integrity`
Hunt had independently confirmed — this time *found* by invariant extraction,
not just capable of converging with something else's finding. It also
surfaced two invariants genuinely new relative to every prior pass on this
project: LemonSqueezy's webhook stamps `datePaid` at processing time while
Stripe/Polar derive it from the event's own timestamp (a real correctness
inconsistency), and a TOCTOU race in Stripe customer creation under
concurrent checkout requests.

The run's own self-honesty check made the mechanism explicit: the missing
idempotency ledger is an *absence* (something not in the schema), not a
locally-visible defect in the code you're reading — noticing it requires
deliberately asking "what happens if this exact event arrives twice" rather
than reviewing each file for what it does wrong in isolation. **This
confirms the attention bias is addressable by prompt design, not an
inherent ceiling on the technique** — but it also means a single generic
extraction pass cannot be assumed to cover every invariant class; different
lenses (authorization, duplicate-input/state-transition, and likely others
still untried) need to be run as distinct passes, not folded into one
generic ask.

## Trial 4 (obs-studio, ~20,571-line C codebase — first test at this scale/language)

The other open gap from trial 2 was untested behavior at large, unfamiliar,
memory-unsafe-language scale. Run against `obsproject/obs-studio`'s
`plugins/obs-outputs/` — the same real-world target as a full prior
domain-based 7-domain audit (see `evals/validation-notes.md` iteration 9) —
again with no knowledge of that prior audit's findings.

Coverage was real and disclosed honestly, not glossed over: only ~20% of the
20,571 lines were read closely (the extraction agent named which files it
prioritized and which ~25% of the codebase, mostly two codec-specific
bitstream parsers, it never opened at all). Within that partial coverage:

- **It independently rediscovered the prior audit's two most severe
  confirmed AMF-decoder findings**, via the same buffer/length-invariant
  lens rather than domain-based Hunt's framing — the third independent trial
  now showing this convergence property, and the first on a large,
  unfamiliar, memory-unsafe C codebase rather than TypeScript/Python.
- **It found two additional real, independently-Verified issues the
  domain-based audit's own `security` Hunt had not surfaced**, in code paths
  a different domain (`architecture`) or no domain at all had touched.
  Technical detail is intentionally not published here — the same
  redaction discipline applies as to every other real vulnerability finding
  in this project's validation record (see iteration 9's own redaction
  note) — but in aggregate severity, both are at least comparable to, and
  one is more severe than, anything the original 7-domain audit found in
  this subsystem. Both went through the same independent adversarial-Verify
  process as every other finding in this project before being counted.
- **Self-honesty check confirmed a real, specific coverage cost**: the two
  invariants the extraction agent itself flagged as least concretely
  grounded ("generic hygiene phrased in codebase-specific language" rather
  than tied to a repeated, verified pattern) going into the checking pass
  were exactly the two that turned out to be violated worst — a genuinely
  useful internal signal (weakly-grounded invariants correlate with where
  gaps actually are), not just a confidence caveat. The agent was also
  explicit that entire subsystems (two codec bitstream parsers, ~1,500
  lines) are not represented in the invariant list at all, simply because
  they fell outside what a single pass had time to reach.

This is the single most consequential result across all four trials: the
technique found real, more-severe-than-previously-known issues in a
widely-deployed real project specifically *because* it isn't scoped by
domain the way Hunt is — a function one domain's Hunt read for one lens
(structure) and another domain's Hunt never re-read for a different lens
(memory safety) fell into exactly the gap between domain boundaries that an
invariant-based pass, run without those boundaries, doesn't have.

## Current standing

Four trials now, not two, closing both gaps identified after trial 2:

- **Attention bias is addressable by prompt design** (trial 3) — but this
  means invocation should explicitly run more than one extraction lens
  (authorization/ownership; duplicate-input/state-transition; likely others
  not yet tried) rather than one generic pass and assuming full coverage.
- **The technique holds up, partially, at large C-codebase scale** (trial 4)
  — convergence with known findings replicated a third time, and it found
  real issues a domain-based audit's own scoping had missed, but only
  covering ~20% of the codebase in the time available. This is not evidence
  it scales *cleanly* to large codebases — it's evidence that even partial,
  time-boxed coverage at that scale still finds real things, which is a
  different and more modest claim.
- False-positive data across all four trials: every VIOLATED/CONDITIONAL
  classification that has been independently adversarially re-verified so
  far has held up (trial 1's fixture-based honesty check aside, which wasn't
  independently re-verified the same way). Still a small, non-random sample
  — every claim verified so far came from a trial run by this same project,
  using this same verification methodology — not grounds for a general
  false-positive-rate claim.

This is now well past "purely speculative" — it has independently found real,
previously-unknown, more-than-domain-based-hunting issues in a real,
widely-deployed piece of software. It remains an **opt-in enhancement**, not
promoted to `SKILL.md` step 1 as a mandatory default: partial coverage at
scale and a still-small, single-project-sourced verification sample are real,
disclosed limits, not resolved ones.

## How to invoke it, now that there's a validated procedure

1. Run the extract-then-check two-pass technique as an additional
   Hunt-shaped pass alongside — not instead of — the relevant domain's
   normal Hunt. Run it as **more than one pass with different explicit
   lenses** when time/cost allows (at minimum: authorization/ownership, and
   duplicate-input/state-transition) rather than one generic extraction
   prompt — trial 3 showed these surface materially different findings from
   the same code. Still: no knowledge of any other domain's findings, and
   the extraction pass fully complete before the checking pass begins.
2. On a large or unfamiliar codebase, have the extraction agent explicitly
   report which files/fraction of the codebase it actually covered — trial
   4's honest coverage disclosure is what made its result trustworthy rather
   than a false "we checked everything" claim, and that reporting should be
   a required part of the output, not an optional nicety.
3. Feed every VIOLATED and CONDITIONAL classification into the normal Verify
   step (`SKILL.md` step 2) exactly like an ordinary Hunt candidate — isolated,
   no visibility into the extraction agent's own confidence or reasoning.
   HELD invariants are not findings and don't need Verify.
4. Report the invariant-derived findings alongside the domain-based ones in
   the same output, tagged as such (e.g. `"source": "invariant-extraction"` on
   the candidate, plus which lens produced it) so a reader can see which
   detection path — and which lens — produced which finding.
