# MVP Validation — Iteration 1

Validates the core mechanism from `SKILL.md`: given a natural-language request and
a real project, can the skill select audit domains adaptively (project-aware, not
just keyword-matching the request), and does it beat what Claude does by default
without the skill?

## Method

4 synthetic fixture projects (`evals/fixtures/`), each paired with a request and run
twice: once with an agent following `SKILL.md`, once with a baseline agent given
only the same request and told to write a plan before acting (no skill). See
`evals/evals.json` for the exact prompts and per-case expectations. Full outputs are
not committed (large, in `iteration-1/` locally) — the comparison below is quoted
directly from the with-skill and without-skill outputs.

## Headline result: eval-3 (`hidden-secret-narrow-ask`)

Request: "レポート生成が遅いので、パフォーマンス改善したい" (report generation is
slow, want a perf fix) — names only performance. The fixture also has a hardcoded
live-looking payment API key and an unauthenticated billing webhook that triggers a
real charge reversal, unrelated to the reporting code path.

**Without skill**, the baseline explicitly scoped security out:

> "I will not do a full audit of the billing code itself, since it's out of scope
> for a performance-of-reporting request ... if I notice something that looks like
> a serious functional or security problem in code I necessarily read along the
> way, I'll flag it briefly rather than silently ignore it."

The hardcoded API key is never mentioned anywhere in the baseline's plan, even
though the plan's own step 1 was "read `app.py` in full" — it was seen and not
flagged as a concrete item.

**With skill**, security was selected as its own plan item (Standard depth) and
placed *first* in execution order, ahead of the performance work the user actually
asked for:

> "security ... 依頼にはないが、支払いAPIキーの平文ハードコード（app.py:8）と、署
> 名検証なしのwebhookが実際の返金処理を叩ける（app.py:33-46）というmoney movement
> 相当のブラストラディウスがあり、フロアスコアで選定（skill step 3）。"

This is the concrete behavior the competitive research flagged as differentiated:
domains with high blast radius (money movement, in this case) are not silently
dropped just because the request was framed narrowly around something else.

## Other 3 cases

- **eval-0** (`webapp-vague-bugcheck`, vague "バグチェックして" on an auth+payment
  app): correctly expanded past a literal "check for bugs" reading — selected
  security (Deep) and data-integrity (Standard) alongside correctness, each backed
  by cited file/line evidence (SQL string-building, missing webhook signature
  check, unbounded balance update). Explicitly excluded performance/concurrency
  with a stated reason (no matching signals), rather than either running everything
  at uniform depth or narrowing to correctness alone.
- **eval-1** (`cli-performance-explicit`, explicit "パフォーマンス見て" on a
  low-risk local CLI): selected performance (Standard) as asked, and *also*
  explicitly recorded that security was checked against the blast-radius rule and
  excluded because no auth/payment/PII signal exists — i.e. the rule fires in both
  directions, it doesn't just add security everywhere.
- **eval-2** (`go-worker-prerelease`, vague pre-release ask on a concurrent queue
  worker): picked up the unprotected shared map in `cache.go` and no-timeout
  handling in `worker.go`, selecting concurrency and reliability at Deep depth
  while keeping security low given no external HTTP surface — depth varied
  per-domain rather than defaulting to one uniform level for a "look at everything"
  request.

## Observed non-goal side effect

The without-skill baselines tended to produce longer, more generic plans (e.g. 148
lines for eval-2, covering README/doc-comment/Go-version hygiene alongside the
actual concurrency risk) rather than a prioritized, evidence-cited list. Not a
formal assertion, but consistent with the research's finding that generic review
approaches don't scope to what actually matters for a given project.

## Conclusion (iteration 1)

The core mechanism (project inspection → domain scoring against a fixed taxonomy →
explicit inclusion/exclusion reasoning) behaves as intended across all 4 cases,
including the adversarial one (eval-3) it was specifically designed to catch.

---

# Iteration 2 — cross-run audit-debt tracking (differentiation area 2)

Validates `scripts/receipts.py` and SKILL.md steps 0/3/6: does the skill actually
read and write its own cross-run history, and does accumulated debt (a domain
repeatedly excluded regardless of how each request was framed) show up as its own
signal, distinct from blast radius?

## Method

`scripts/receipts.py` was first tested directly (no LLM) against a synthetic
two-receipt history: a domain audited twice at Quick depth only, one audited Deep
once then not since, and one just audited Deep. `debt` correctly ranked the
never-Deep domain highest and the just-audited one lowest — confirms the ranking
logic itself before trusting an agent to use it correctly.

Then `eval-4` (`go-queue-worker` fixture, history cleared first) ran two real
agent turns in sequence, each actually executing the skill's step 0/6 script
calls (not simulated):

- **Run A**: "テストとドキュメントを確認して" (narrow ask: tests + docs).
- **Run B**: "一通り見て" (vague, generic ask), same project, run after A.

## Result

Run A correctly reported `total_runs: 0` (first run for this project — no history
to read yet), scored domains from project signals alone, selected
concurrency/test-coverage (deep), reliability (standard), observability (quick),
excluded security/dependency-health, and wrote a receipt — confirmed by re-running
`debt` afterward and seeing `total_runs: 1`.

Run B correctly read that receipt (`total_runs: 1`) and reported it back
accurately per-domain (times selected/excluded, `max_depth_ever`,
`runs_since_last_deep`) in a new "過去の監査履歴" section, then used it as a
scoring input alongside step 2's fresh project inspection — not as an override:

> "security ... 過去実行でも除外(0/1選定)、runs_since_last_deep=1で除外が2回連続
> となる点は債務として記録。"
> "dependency-health ... 過去実行でも同様に除外(0/1選定)。... これは『見落とし』
> ではなく『対象不在』による判断。"

This is the distinction the design was aiming for: `security` has no supporting
project signal in this fixture (internal-only service, no PII/payment code) so
debt alone didn't flip it to selected — but the run explicitly flagged the
exclusion streak as debt to revisit if the project's nature changes, rather than
silently repeating the same exclusion with no memory of having done so before.
`dependency-health`, by contrast, was correctly recognized as *structurally*
out of scope (no third-party dependencies exist at all — `go.mod` has no
`require` block) rather than debt, showing the two "always excluded" domains
aren't treated identically just because they share a stats pattern.

`plan_record` in both runs listed all 11 taxonomy domains (selected and excluded)
with reasoning and evidence, as step 6 requires — confirmed by inspecting the
written receipt files directly, not just the agent's own claim.

## Conclusion (iteration 2)

The audit-debt mechanism works end-to-end through a real agent turn, not only in
the standalone script test: history is read, reported honestly, used as a scoring
input, and re-written afterward, and the model correctly distinguished
"repeatedly excluded because still no evidence" from "repeatedly excluded because
structurally inapplicable" rather than treating every debt-accumulating domain the
same way. No changes made to `SKILL.md`/`scripts/receipts.py` after this
iteration — shipping as-is.

## Next validation round from iteration 2 (still not run)

- A case with genuinely no elevated-risk signal anywhere (does it correctly
  produce a short, low-domain-count plan instead of padding it out?).
- A case where the request explicitly asks to skip a domain the project clearly
  needs (does the skill respect an explicit exclusion, or override it the same
  way it overrides silence?).
- A longer history (5+ runs) with a domain that keeps sitting just under the
  "worth mentioning" bar — does accumulated debt eventually flip it to selected,
  or does the bump prove too weak in practice to ever matter?

---

# Iteration 3 — adaptive-audit-execute (Hunt → Verify)

Validates the second skill: given a plan, does it actually find real, confirmable
issues in the domains the plan selected, and does the Verify pass genuinely reject
bad candidates rather than rubber-stamp the hunt? Also extends `receipts.py` with
execution results (linked to their plan via `plan_id`) and re-validates `debt`
distinguishes *planned* depth from *verified* depth.

## Method: script extension (no LLM)

Manually exercised the new `write-result`/updated `debt` commands against the
`webapp-auth-payment` fixture: wrote a plan selecting `security` at deep, checked
`debt` (correctly showed `max_verified_depth_ever: null` — planned deep, nothing
verified yet), then wrote an execution result for `security`, checked `debt` again
(`max_verified_depth_ever: "deep"` — now correctly reflects verified work). Also
confirmed `write-result` refuses an unknown `--plan-id` rather than silently
creating an orphaned result.

## Method: eval-5, real agent run

One real agent turn followed `adaptive-audit-execute/SKILL.md` against
`webapp-auth-payment` (history cleared first) with "バグを実際に見つけて直したいので、
監査を実行して" (I want to actually find and fix the bugs). No plan existed yet, so
the agent generated one first (per the skill's own step 0), then executed Hunt →
Verify across the 8 selected domains.

## Result: finding quality

Correctly CONFIRMED every vulnerability deliberately seeded in the fixture: two
SQL-injection sites (`auth.js:9-10`, `payments.js:13-14`), the missing Stripe
webhook signature check, the entirely-missing password check in `login()`, the
unwrapped two-write payment transaction, missing error handling around DB calls
in an Express-4 app (a real crash risk, not a style nit), and missing webhook
idempotency (double-credit risk) — each with a concrete file/line and failure
scenario, not a vague risk statement.

More importantly, **the Verify pass genuinely rejected two hunt candidates**,
not zero: a claimed "auth bypass via missing Authorization header" (verify
correctly traced that `jwt.verify` throws synchronously into an enclosing
`try/catch`, so it 401s rather than bypassing or crashing), and a claimed
"connection pool leak" (verify correctly recognized `pool.query()` as the
standard long-lived-pool usage pattern, not a leak). A pipeline that confirms
everything the hunter proposes isn't doing real verification — these two
rejections are the actual evidence that step 2 is adversarial rather than
decorative.

## Result: an honest limitation surfaced, not hidden

The skill's design calls for Hunt and Verify to run as physically separate
subagents. In this test, no subagent-spawning mechanism was available inside the
nested test-agent's own tool surface (no Task tool; a `create_session` fallback
attempt was blocked by the permission classifier). Rather than silently proceeding
as if isolation had happened, the agent disclosed this explicitly in the output's
実行サマリー and fell back to two clearly-separated same-session passes, actively
attempting to disconfirm each candidate in the second pass rather than reasoning
forward from the first.

This is the right failure mode, but it means **this run only validates the
same-session fallback, not true cross-agent isolation** — the isolation itself
(the thing that most protects against a hunter and verifier sharing the same
anchoring bias) is unvalidated. `SKILL.md` step 1 was updated after this run to
make the fallback an explicit, required disclosure rather than something the
model had to improvise correctly on its own; the output format's 実行サマリー now
explicitly requires stating which mode was used.

## Conclusion (iteration 3)

Finding quality and the Verify pass's willingness to reject are both validated
with concrete evidence (13 confirmed, 3 plausible, 2 rejected, all individually
inspected above). The cross-run receipt linkage (plan → execution result via
`plan_id`) works, confirmed both by direct script testing and by the real run.
**Not yet validated**: Hunt/Verify under true subagent isolation — this needs a
re-run in an environment where a real Task-tool-equivalent is available to the
executing agent (e.g. an actual Claude Code CLI session rather than this
harness's nested test-agent), to confirm the fully-isolated path behaves at least
as well as the disclosed fallback did here.

---

# Iteration 4 — true isolation, a harder fixture, and a baseline comparison

Closes the three gaps iteration 3 flagged: real cross-agent isolation (not the
same-session fallback), a fixture that doesn't announce its own bugs in
comments, and a with/without-skill comparison for the *execution* phase (the
plan-generation phase already had this in iteration 1; execution didn't).

## Method

**Isolation, done correctly this time.** Iteration 3's isolation failure came
from testing one layer too deep: a spawned test-agent tried to spawn further
subagents of its own and had no tool to do that with. This time the orchestrating
session itself (the one with real subagent-spawning capability) drove the
Hunt/Verify process directly — 6 real, independent Hunt agents (one per
selected domain), then 6 real, independent Verify agents (one per domain's
candidate set) — genuine cross-agent isolation, not a nested simulation of it.

**New fixture: `task-api`** (`evals/fixtures/task-api/`) — a small Flask
task/todo API with 6 deliberately seeded issues, written with **no comments
announcing any of them** (unlike earlier fixtures, which sometimes had
`// no signature verification` -style tells): an IDOR (no ownership check on
task read/update), a check-then-act race in a claim-next endpoint, a `status`
field with no validation that desyncs from a paired `claimed_by` field, a
hardcoded JWT secret + hardcoded internal API key, plaintext password storage,
and unguarded `request.json[...]` access that 500s on malformed bodies.

**Baseline**: a separate agent, no skill, asked to actually find bugs (not just
plan) against the same fixture.

## Result: baseline was strong, but missed something real

The no-skill baseline found most of the seeded issues on its own, including the
IDOR — small self-contained fixtures are not a hard case for Claude's default
code-reading ability, and this needs to be stated plainly rather than undersold.
What it did *not* find: a `RuntimeError: dictionary changed size during
iteration` hazard from `claim_next`/`summary()` iterating the shared task dict
while `create_task` concurrently inserts into it — a real, non-obvious
concurrency bug distinct from the more obvious double-claim race. The with-skill
run's concurrency Hunter found it, and Verify then **empirically reproduced it**
(wrote and ran an actual multi-threaded stress script — 7 real exceptions raised
in a 5-second run) rather than taking the claim on trust.

## Result: Hunt → Verify at scale, with real empirical testing

29 total candidates across 6 domains: **27 CONFIRMED or PLAUSIBLE, 1 REJECTED**
(module-level ID counter — Verify correctly recognized `itertools.count`'s C-level
`__next__` as atomic under the GIL, so the hunter's own "future risk" framing
doesn't describe a present bug), **1 downgraded from an implied bug to PLAUSIBLE**
(a claimed "lost writes" issue in `update_task` — Verify determined `dict.update`
is a single atomic operation, so it's ordinary last-write-wins semantics, not
data corruption). Both of these are genuine, technically precise skepticism, not
arbitrary rejection quotas.

The security Hunter, running at Deep depth, went further than reading code: it
stood up a sandboxed local Flask instance and **actually executed** the exploit
chain (forged a JWT with the hardcoded secret for a nonexistent user, used it to
read and tamper with another user's task via the IDOR, hit the internal-report
endpoint with the hardcoded key copied from source) rather than reasoning about
whether it would work.

## Conclusion (iteration 4)

True cross-agent isolation is now validated, not just designed — the earlier
same-session fallback is confirmed to have been a testing-harness artifact, not
a property of the skill itself. The skill measurably found something a
same-size no-skill baseline missed, on a fixture designed specifically not to
hand over the answer. Verify's rejections/downgrades on this run were both
correct and specific (an atomic dict op, an atomic C-level counter increment) —
evidence of real technical reasoning, not a fixed "reject N%" pattern.

---

# Iteration 5 — Audit Plan self-verification (SKILL.md step 5)

Validates the new step closing gap #37 from the competitive research: nothing
found anywhere in 22+ surveyed repos adversarially reviews the *plan* itself,
only findings. Tested by handing an isolated critic a deliberately flawed plan
(not generated by the skill — hand-authored to contain a specific, findable
depth-mismatch and a specific, findable exclusion that contradicts the signals)
and checking whether it's caught rather than rubber-stamped.

## Result

The critic correctly:
- Flagged `security` at `quick` depth as under-assigned given signals that
  require logic-level review to find (the IDOR), not just a secrets grep — and
  named exactly which two signals the stated reasoning had silently dropped.
- Flagged `concurrency`'s exclusion ("no signal found") as factually
  contradicted by a signal literally describing an unsynchronized check-then-act
  race, not a judgment call to weigh.
- Found a signal ("no logging calls anywhere") that mapped to no domain in the
  table at all, because the domain it would belong to had been excluded for an
  unrelated reason.
- **Distinguished** the concurrency exclusion (factually wrong — reject) from
  the `test-coverage` exclusion ("not explicitly requested" — a defensible
  policy stance the critic disagreed with but didn't call an error). This is
  the same category of nuance validated in iteration 2's debt tracking
  (neglected vs. structurally inapplicable) — the mechanism isn't just finding
  things to complain about.

## Conclusion (iteration 5)

The plan self-verification step behaves as intended on a test built specifically
to have a right answer: it caught both planted flaws, named the exact
contradicting signal for each, and correctly separated "wrong" from
"debatable." Not yet tested: a well-formed plan with no injected flaws, to
confirm the critic doesn't manufacture objections when there's nothing to
object to (a false-positive-rate check, not just a sensitivity check).

---

# Iteration 6 — Invariant extraction (experimental)

The highest-risk, most novel item from the original research — essentially
unattempted anywhere in the ecosystem (one 0-star, unused prior attempt).
Tested once, kept deliberately out of the default pipeline regardless of
outcome (see `adaptive-audit-execute/references/EXPERIMENTAL-invariant-extraction.md`
for the full write-up and why it stays experimental).

## Result

Asked to extract invariants from `task-api` with no knowledge of its seeded
bugs and no access to tests/docs (there are none), a single run produced 9
invariants purely from code structure, then checked each against the code:
6 violated, 2 held, 1 conditional. Two of the violations — task ownership and
the `status`/`claimed_by` pairing — independently converged on the exact same
bugs the domain-based Hunt already found, via a completely different reasoning
path (top-down "what must hold" vs. bottom-up "what looks wrong"). Asked
explicitly to self-assess rather than claim uniform success, the run reported
6 of 9 invariants as tightly grounded and cleanly checkable, and the other 3 as
leaning on generic security hygiene more than on anything the code specifically
implied.

## Conclusion (iteration 6)

One run is evidence the technique is *tractable* on a small, single-purpose
codebase and can independently corroborate findings from the domain-based
pipeline — not evidence it's ready to ship. No data exists yet on cost at
scale, behavior on a large/architecturally varied codebase, or false-positive
rate on a confidently-stated "violated invariant" claim. Stays experimental and
undocumented-by-default per the research's own original risk assessment; a
design sketch for eventual integration (as a second, independent angle inside
Verify, not a replacement for domain-based hunting) is recorded in the
experimental reference file for whenever it's judged worth the validation cost
of pursuing further.

---

# Addendum — `export-csv`

Added after the user pointed out an HTML dashboard mockup isn't actually
shareable. Rather than adding a PDF or XLSX writer (both need a third-party
dependency, breaking this script's stdlib-only design), `export-csv` reuses
the exact same `_compute_debt` computation `debt`/`report` already use and
writes it as CSV — opens directly in Excel/Sheets with no conversion step.
Manually verified against the real `task-api` history: header + 10 domain rows,
correct status/depth/count values matching `report`'s own output for the same
data. A PDF, when actually needed to hand to someone, is left to Claude to
render from this CSV or from `report`'s text on request, rather than being a
feature of the script itself.

---

# Iteration 7 — real-world routing test, and a real design bug it found

Two real-world tests against an actual, unrelated published project
(`kajisho5/ffmpeg-skill`, a working copy with both skills installed under
`.claude/skills/`, original clone never touched) rather than a synthetic
fixture — both run by giving an agent only a plain request and a read-only
constraint, with no mention of "adaptive-audit" or any SKILL.md, to test
whether the skills are actually discovered and used the way a real user's
session would, not just when explicitly pointed at.

## Run 1 (before this iteration's fix): a real gap found

Request: "このプロジェクトをバグチェックして。読み取り専用で、絶対にファイルを
変更・作成・削除しないこと。" The agent found and read `adaptive-audit-plan` on
its own — skill discovery works — but then **declined to use it**, because its
mandatory `receipts.py write` step had no way to honor "don't touch anything,"
and silently ignoring that constraint or violating it were the only two options
available. It fell back to a manual review instead. The skill fired correctly
and still contributed nothing to that run.

Fix: added a dry-run mode to both skills (a read-only/no-side-effects request
skips only the receipt/result-writing steps; the actual scoping and hunt/verify
work still run and still produce real output) — see the "Addendum" above for
`export-csv`, which landed around the same time; the dry-run mode itself is
documented directly in both `SKILL.md` files' step 1/step 0.

## Run 2 (after the dry-run fix): confirms it, and confirms Plan quality on real code

Same request, same project, skills refreshed with the dry-run fix. This time
the agent actually engaged `adaptive-audit-plan`, correctly declared dry-run
mode, and produced a plan covering 7 of 11 domains — correctly excluding
concurrency/performance/dependency-health/observability with real, specific
reasoning (no threading found anywhere, zero runtime dependencies, no async
workers). The plan's security selection was grounded in something the domain-
signal taxonomy couldn't have invented: a filter-graph injection vulnerability
class **documented in the target project's own code comments** as a previously
real, fixed defect (`validate_color()`'s docstring) — used as evidence that the
same defect class might recur elsewhere in ~30 files building similar filter
strings. The self-critique step (no subagent isolation available, so run as an
in-context adversarial re-read per the documented fallback) caught a genuine
gap the initial pass missed: `bin/install.js` deletes and recreates its install
target non-atomically, evidence neither `correctness` nor `reliability` had
originally cited. Cost: 147K tokens, 17 tool calls, 0 subagents, ~5.8 minutes,
for planning only, on a real ~8,300-line, 40-script project.

## The bigger problem this surfaced: the user was right that this shouldn't require two commands

Run 2 stopped after the plan, per `adaptive-audit-execute`'s own description at
the time, which explicitly told Claude to treat a bare "バグチェックして" as an
`adaptive-audit-plan`-only case and wait for a separate, explicit "now run it."
That directly contradicts this project's founding premise (a single
natural-language request produces a complete audit, no follow-up question
required) — a two-step "get a plan, then separately ask to run it" flow is
exactly the configure-then-run friction the project set out to remove, and it
was reintroduced by a description-level decision made mid-project for
cost-control reasons, not a limitation of the underlying mechanism (which
already auto-generates its own plan when none exists).

Fixed by flipping the default: `adaptive-audit-execute` is now the skill a
bare, unqualified request routes to (see both `SKILL.md` frontmatter
descriptions); `adaptive-audit-plan` is the explicit-opt-in case for someone
who specifically wants only the scoping decision. Cost control for the (now
default) full pipeline is left to the plan's own per-domain depth assignment
rather than an extra stop-and-ask gate layered on top of it.

## Run 3 — confirms the routing fix, end to end, on a fresh project

New fixture-based project (a copy of `go-queue-worker`, fresh history), bare
request "バグチェックして", no other signal, both updated skills installed.
The agent correctly reasoned that `adaptive-audit-execute`'s description now
names this exact case as its target and that using `adaptive-audit-plan` alone
would be the wrong choice, then ran the full pipeline in one response: plan →
Hunt → Verify → both receipts written. Found a real CONFIRMED crash (`fatal
error: concurrent map writes` from unsynchronized goroutine access — the
process-ending kind, not a recoverable panic) and a real CONFIRMED missing
`recover()` around the worker loop, correctly downgraded two speculative
candidates to PLAUSIBLE, and correctly REJECTED a candidate ("no timeout on
downstream calls") once it verified the referenced code was an unimplemented
stub with no downstream call to time out yet — precise, not just permissive,
skepticism. Cost: 102K tokens, 19 tool calls, ~4 minutes, single response,
5 domains executed.

## Conclusion (iteration 7)

Both real-world tests did what they were for: found a real, load-bearing design
gap (no way to honor a legitimate "don't touch anything" request) and a real,
project-level UX gap (the two-command flow contradicting the founding premise)
that no synthetic-fixture eval had surfaced, because both gaps are about how
the skills present themselves and route requests, not about the quality of
their internal reasoning. The reasoning itself held up well on real,
unfamiliar, substantial code in both runs. Still open: real Hunt/Verify cost
data on a large real repository (run 2 stopped at planning; run 3 was a small
fixture) — that number is still only known for a tiny synthetic fixture
(task-api, ~660K tokens across 6 domains) and remains the next real unknown.
