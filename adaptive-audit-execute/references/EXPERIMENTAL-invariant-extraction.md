# EXPERIMENTAL: Invariant Extraction

**Status: experimental, not part of the default `adaptive-audit-execute` pipeline.**
Do not invoke this during a normal run unless the user has explicitly asked for
invariant-based analysis. This is deliberately kept separate rather than wired
into step 1 of `SKILL.md` — see "Why this is separate" below.

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

## Why this is separate from the default pipeline

- **One validation run is not enough** to trust as a default step that changes
  what every audit surfaces. The competitive research explicitly flagged this
  as the highest-risk, least-proven idea in the original concept — that
  assessment doesn't change just because one run went well.
- **No cost/scale data.** This hasn't been tried on a codebase large or varied
  enough to know if the technique degrades, or how much it costs in tokens/time
  relative to the value added over domain-based hunting alone.
- **No False-positive-rate data.** A confidently-stated "violated invariant"
  that turns out to be wrong is arguably worse than a missed one, because it's
  phrased as a stronger claim ("this must always be true, and it isn't") than
  an ordinary finding. That failure mode hasn't been tested for.

## If this graduates out of experimental status

The natural integration point is as a cross-check inside `adaptive-audit-execute`
step 2 (Verify): a verifier could additionally ask "does this candidate finding
correspond to a violated invariant, or only a preference?" — giving Verify a
second, independent angle to confirm or downgrade a Hunt candidate from, on top
of re-deriving it from source. That is a design idea, not something implemented
here.
