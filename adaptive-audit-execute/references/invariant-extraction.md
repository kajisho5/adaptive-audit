# Invariant Extraction (opt-in enhancement)

**Status: validated across two independent trials, but still opt-in — not
part of the default `adaptive-audit-execute` pipeline.** Do not invoke this
automatically during a normal run; use it when the user has explicitly asked
for invariant-based analysis, or when `security` is selected at Standard/Deep
depth and you judge the extra scrutiny worth the roughly-one-domain's-worth of
additional cost (see "Trial 2" below for real numbers). This is deliberately
kept out of `SKILL.md` step 1 as a *default* step rather than promoted to one
— see "Current standing" below for exactly what has and hasn't been shown.

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

## Current standing

What trial 2 adds beyond trial 1: real-project scale (not just a small
fixture), real cost data, a tested false-positive-check methodology (even if
the sample is still small), and — most importantly — the first concrete case
of the technique finding something a full domain-based audit missed, at
comparable cost to that domain's own process. That's enough to move this from
"purely speculative, don't use it" to **a validated opt-in enhancement worth
reaching for on the `security` domain specifically at Standard/Deep depth**,
not enough to promote it into `SKILL.md` step 1 as a default step for every
run or every domain:

- Only 2 trials total, both scoped to auth/access-control-shaped invariants —
  never yet tried with an extraction prompt aimed at correctness, reliability,
  or data-integrity-shaped invariants (e.g. "what must be true about how this
  system handles a duplicate/retried input" — exactly the class this trial's
  own attention-bias finding shows it currently under-produces).
- Still no data on how the technique degrades on a codebase large enough that
  "what does this pattern imply" stops being answerable from a single
  focused read-through (obs-studio-scale, ~20K+ lines, hasn't been tried).
- `n=2` false-positive-rate data point is a real signal, not a rate.

## How to invoke it, now that there's a validated procedure

1. Run the extract-then-check two-pass technique described above (still: no
   knowledge of any other domain's findings, extraction pass fully before the
   checking pass) as an additional Hunt-shaped pass alongside — not instead of
   — the `security` domain's normal Hunt.
2. Feed every VIOLATED and CONDITIONAL classification into the normal Verify
   step (`SKILL.md` step 2) exactly like an ordinary Hunt candidate — isolated,
   no visibility into the extraction agent's own confidence or reasoning.
   HELD invariants are not findings and don't need Verify.
3. Report the invariant-derived findings alongside the domain-based ones in
   the same output, tagged as such (e.g. `"source": "invariant-extraction"` on
   the candidate) so a reader can see which detection path produced which
   finding — that distinction is itself useful signal, not overhead to hide.
