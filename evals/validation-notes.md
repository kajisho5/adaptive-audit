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
outcome (see `adaptive-audit-execute/references/invariant-extraction.md`
for the full write-up; this trial is trial 1 there, followed up by trial 2
in iteration 12 below).

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

## Iteration 8 — full real-world audit against `kajisho5/ffmpeg-skill` (the routing fix's first full-scale run)

Following the routing fix above, `adaptive-audit-execute`'s complete plan → Hunt
→ Verify pipeline was run against the real, unmodified `kajisho5/ffmpeg-skill`
repository (~8,300 lines, 40 scripts) with true cross-agent subagent isolation
throughout (every Hunt and Verify pass a fresh agent dispatched directly by the
orchestrating session, not a same-session fallback). Read-only end to end,
verified via `git status`/`git rev-parse` before and after.

7 domains executed at the depths the self-critiqued plan assigned
(security/correctness Deep, architecture/data-integrity/reliability/test-coverage
Standard, configuration-deployment Quick). All 22 findings that survived Verify
came back CONFIRMED (one further candidate was independently CONFIRMED on its
core claim but had a specific proposed attack sub-path tested against a real
libass rendering and found not to work — reported as partially confirmed rather
than silently dropped or overstated). configuration-deployment came back clean
(no findings, correctly reported as such rather than padded).

**Headline result, redacted here**: the security domain, at Deep depth, found
and *reproduced* (actual execution in an isolated `/tmp` sandbox, not just
static reasoning) a real, currently-unpatched arbitrary-code-execution path in
one of the project's own scripts. Full technical detail is intentionally not
included in this public file while a fix is pending — this is the repo owner's
own software, and the finding is being handled directly with them outside this
document. The result is recorded here because it's real evidence the pipeline
finds serious, non-superficial bugs on real code, not because the mechanism
itself needs any change.

**Cost** (real, measured): plan self-critique ~63K tokens; Hunt (7 domains)
~1.13M tokens; Verify (6 domains that produced candidates) ~510K tokens.
**Total ≈ 1.7M tokens** for a ~8,300-line, 40-script real project across 7
domains at a Quick/Standard/Deep mix. This answers iteration 7's open question:
real Hunt/Verify cost on a substantial real repository, not a small fixture.

## Iteration 9 — stress test at 2.5x scale, third-party C/C++ project: `obsproject/obs-studio`

A further real-world run against a large, third-party (not the user's own),
widely-deployed open-source C/C++ project — `obsproject/obs-studio`, scoped to
`plugins/obs-outputs/` (~20,571 lines) — to test whether the same methodology
holds up on unfamiliar, larger, memory-unsafe-language code with a completely
different threat model (network-facing protocol/binary-format parsing, not a
scripting-language CLI tool). Read-only throughout, true cross-agent isolation,
same plan → self-critique → Hunt → Verify pipeline.

The plan's own self-critique step caught two real defects in the *plan itself*
before any Hunt ran: a depth assignment (concurrency) that under-weighted a
structurally strong signal relative to a thinner one elsewhere, and an excluded
domain (architecture) whose stated exclusion reason directly contradicted a
signal cited elsewhere in the same plan — both were fixed before Hunt began, not
just noted and ignored, which is exactly what this step exists to catch.

7 domains executed at plan depth (security/correctness Deep; dependency-health/
reliability/concurrency Standard; test-coverage/architecture Quick). Of 28
candidates that survived to Verify: 22 CONFIRMED, 1 PLAUSIBLE (a real,
unpatched code match to a historical, publicly-disclosed CVE, but Verify traced
the actual reachable value range in this codebase and found the specific
integer-overflow exploitation path isn't currently reachable), and 2 REJECTED —
one of which is worth calling out specifically: a claimed use-after-free that
Verify traced up through the host application's own synchronization layer (a
real mutex+condvar-backed gate one level above the file the Hunter examined)
and found the race window the claim needed does not actually exist through the
public API, despite the raw field-level analysis being accurate. That's the
adversarial-Verify mechanism working exactly as intended — not rubber-stamping
a plausible-sounding claim, and not over-rejecting a real one either, since the
other five concurrency candidates in the same batch were independently
confirmed as genuine races.

**Redacted for the same reason as iteration 8**: the security domain found two
independently-reproduced (AddressSanitizer-confirmed against the real,
unmodified source) memory-safety bugs reachable pre-authentication from any
RTMP server a user connects to. This is a large, third-party project with a
formal coordinated-disclosure program (RCE explicitly in scope, 120-day
confidentiality window) — full technical detail is deliberately not published
here or anywhere else; it is being routed through the project's official
security contact instead, per their own stated policy.

One environment-specific process note: the first Verify attempt for the
security domain was interrupted mid-run by this execution environment's own
automated cyber-content safety filter — a false-positive interruption of
legitimate, authorized defensive code review (rebuilding an AddressSanitizer
test harness), not a finding about the audit itself. Re-running with a
verification prompt that leads with static/manual source tracing rather than
harness-rebuilding completed successfully and reached the same conclusions.
Worth knowing for future runs against security-sensitive C/C++ code: front-load
static reasoning in the Verify prompt, treat dynamic PoC-building as optional
and secondary.

**Cost** (real, measured): plan self-critique ~55K tokens; Hunt (7 domains)
~914K tokens; Verify (7 passes, including the interrupted-and-retried security
pass) ~557K tokens. **Total ≈ 1.53M tokens** for ~20,571 lines across 7 domains
— notably *not* proportionally higher than iteration 8's ~1.7M tokens for an
~8,300-line project, despite being ~2.5x the code size. This suggests audit
cost tracks structural/attack-surface density more than raw line count: a large
fraction of this codebase's bulk is repetitive protocol-phase or binary-format-
writer boilerplate that doesn't need the same scrutiny per line as its smaller,
denser, more attack-surface-rich counterparts.

## Conclusion (iterations 8-9)

Two full real-world runs at meaningfully different scales (8.3K and 20.5K
lines), languages (Python and C), and threat models (a local CLI tool's
scripting surface vs. a network-facing C parser in widely-deployed software)
both produced real, non-superficial, independently-reproduced findings — not
just plausible-sounding candidates that Verify waved through. Both also
produced at least one case of Verify genuinely overturning or narrowing a
Hunter's claim rather than confirming everything handed to it (iteration 8's
libass-tested-and-failed sub-claim; iteration 9's traced-out use-after-free and
downgraded CVE-exploitability claim), which is the concrete evidence this
project's differentiation claim (adversarial Verify, not just a second opinion
that agrees) actually holds under real, unfamiliar code rather than only on
synthetic fixtures built to demonstrate it.

## Iteration 10 — staged depth escalation (`depth_confidence` + Quick-first for provisional domains)

Iterations 8-9's real cost data (~1.7M and ~1.53M tokens for full Deep/Standard
multi-domain runs) motivated a design change: a domain assigned Standard/Deep
depth purely from a domain's generic baseline reasoning (no specific signal
pointing at *this* project) shouldn't automatically cost a full Standard/Deep
Hunt pass. `adaptive-audit-plan` now records a `depth_confidence`
(`high`/`provisional`) alongside any Standard/Deep depth assignment, and
`adaptive-audit-execute`'s Hunt step (1) runs `high`-confidence domains straight
at their planned depth as before, but (2) runs a `provisional` domain's planned
Standard/Deep depth as a cheap Quick pass first, escalating to the full depth
(seeded with the Quick pass's own candidates, not discarding that work) only if
the Quick pass actually found something, and otherwise stopping at Quick.

**A real latent bug surfaced while designing this, fixed in the same change**:
`receipts.py`'s debt calculation resolved a result's verified depth by looking
up the *plan's* depth for that domain, never checking the result record itself.
A domain that stopped at Quick under the new staged-escalation rule would have
been silently miscounted as verified at its full planned depth — exactly the
failure mode the whole receipts mechanism exists to prevent. Fixed by adding a
`depth_executed` field to the result-record schema (the depth Hunt actually
ran at) and having the debt calculation prefer it, falling back to the plan's
depth only for result records written before this field existed.

**Validation** (proportionate to the change — not a full 7-domain real-world
audit, since that wasn't needed to validate this specific mechanism):
- Two deterministic unit tests against `receipts.py` directly: (a) a
  Quick-confirmed staged-escalation stop is recorded as `max_verified_depth_ever
  == "quick"`, not the plan's `"deep"`; (b) an old-style result record with no
  `depth_executed` field still falls back to the plan's depth correctly
  (backward compatible with every result recorded before this change).
- One real, cheap fixture run (`evals/fixtures/cli-data-processor/`, ~31 lines)
  exercising both branches with true isolated Hunt subagents: `performance`
  assigned Standard/`high` (an explicit, already-commented O(n·m) scan pattern)
  ran straight to Standard and found 2 real findings; `correctness` assigned
  Standard/`provisional` (generic baseline only) ran Quick first, found 3
  candidates, and correctly escalated. The escalated Standard pass, seeded with
  the Quick candidates, refined them, correctly ruled out one hypothesis it was
  asked to double-check (a suspected row/label misalignment — confirmed not a
  bug), and found one additional real issue the Quick pass had missed
  (duplicate lookup-table ids silently resolved by file order via `iloc[0]`) —
  i.e. escalation isn't just "run it again," it demonstrably builds on and goes
  beyond the cheap first pass. Receipts written for the run confirmed the debt
  report shows both domains correctly as verified at `standard` (matching the
  depth actually reached after escalation, not the intermediate Quick stage).

Known limitation not yet tested: the *cost savings* case (a `provisional`
domain whose Quick pass genuinely finds nothing and correctly stops there,
saving a full Standard/Deep pass) wasn't exercised against a real project in
this validation — both real projects audited so far (iterations 8-9) predate
this feature, and the one live fixture run here happened to escalate. Worth
confirming on the next real-world run that a stop-at-Quick case is disclosed
correctly in the 実行サマリー and doesn't get mistaken for a full clean result.

## Iteration 11 — first real "typical webapp" (auth + payment + DB) run: `wasp-lang/open-saas`

Closes the gap iteration 7 first identified: every prior real-world run had
been a CLI tool (ffmpeg-skill), a large C/C++ project (obs-studio), or a small
synthetic Go fixture — never the auth+payment+DB "typical webapp" shape the
project's own original synthetic fixture (`webapp-auth-payment`) was modeled
on. This run picked a real one: `wasp-lang/open-saas` (15.7K GitHub stars, MIT
licensed, actively-maintained SaaS boilerplate many real production products
fork directly), scoped to `template/app/` (~10,895 lines: React/Node/Prisma
via the Wasp framework, 3 supported payment processors, file upload, an admin
panel). Read-only throughout, true cross-agent isolation, same
plan→self-critique→Hunt→Verify pipeline, verified via `git status`/`git
rev-parse` before and after.

This is also the first real-world run to exercise iteration 10's staged
depth-escalation feature on a genuine audit rather than a demonstration
fixture. The plan's `test-coverage` domain was assigned Standard depth with
`depth_confidence: provisional`; its Quick-first pass found 2 candidates and
correctly escalated, and the escalated Standard pass — seeded with the Quick
findings — refined and expanded them to 4, adding real severity information
(concretely, which of 3 supported payment processors have zero test coverage
of any kind) the Quick pass alone hadn't captured. Still open from iteration
10: a real-world case of a provisional domain finding nothing at Quick and
correctly stopping there hasn't been observed yet — this run's one provisional
domain also escalated.

The plan's self-critique step caught two real defects before Hunt began: a
domain (`correctness`) whose justification cited a concrete signal that hadn't
actually been disclosed to the critic (a real signal from the planner's own
inspection, procedurally omitted rather than fabricated — fixed by stating it
properly), and a domain (`configuration-deployment`) whose justification
padded a weak core signal with other undisclosed evidence (fixed by dropping
the domain and folding its one legitimate observation into `security`
instead). A third objection — bump `data-integrity` from Standard to Deep
given how confirmed its evidence already was — was accepted. A fourth
objection, that `test-coverage`'s Standard depth contradicted its own
"provisional" confidence label, was examined and rejected: provisional-
confidence Standard is the intended trigger for staged escalation, which the
critic prompt hadn't explained — a process lesson (explain the mechanism to
the critic next time), not a plan defect.

6 domains executed (security/data-integrity Deep, correctness/reliability/
test-coverage Standard, dependency-health Quick). Of 19 candidates that
survived to Verify: **18 CONFIRMED, 1 downgraded to PLAUSIBLE, 0 rejected** —
the highest single-run confirmation rate of any real-world audit so far
(compare obs-studio's 22/28 with 2 rejected), plausibly because this plan's
signals came from unusually thorough direct pre-inspection before Hunt began
rather than pattern-matching alone. Two security candidates were independently
found by Verify to be *more* severe than the Hunter had scoped them (one
turned out to have no `context` parameter at all, not just an unchecked one;
the other chains into an actual delete of a victim's file, not just
unauthorized listing) — concrete evidence the adversarial-Verify mechanism
isn't systematically biased toward leniency, since it has now been observed
doing all three things a real skeptic should: confirming, rejecting (obs-
studio), and escalating severity (here).

**Redacted for the same reason as prior iterations**: findings include a
confirmed, unauthenticated file-access bug and a confirmed payment-webhook
idempotency gap enabling real credit duplication — both have genuine abuse
potential in a template forked into real billing systems. This repository has
no `SECURITY.md` of its own; the maintaining team's contact (published on the
main framework repo) was used to prepare a private disclosure draft instead of
filing a public issue or publishing detail here.

**Cost** (real, measured): plan self-critique ~56K tokens; Hunt (6 domains
plus one escalation pass) ~590K tokens; Verify (6 passes) ~408K tokens.
**Total ≈ 1.05M tokens** for ~10,895 lines across 6 domains at a Quick/Standard/
Deep mix — the cheapest full real-world audit so far, consistent with
iteration 9's observation that cost tracks signal/attack-surface density more
than raw line count: this run's domain selection was unusually tightly
targeted (every Standard/Deep domain had `depth_confidence: high` except the
one that used staged escalation), so little Hunt effort was spent on
low-yield areas.

## Iteration 12 — invariant extraction, trial 2 (real project, second independent trial)

Follow-up to iteration 6's single trial (a synthetic fixture), addressing the
three gaps that kept the technique purely experimental: no test at real-
project scale, no cost data, no false-positive-rate data. Run against the
same `wasp-lang/open-saas` project as iteration 11, scoped to auth/payment/
file-upload/user/admin, with the extraction agent given **no knowledge of
iteration 11's findings**. Full write-up and the resulting graduation
decision live in `adaptive-audit-execute/references/invariant-extraction.md`
("Trial 2" section) — summarized here for the audit-log record:

- 12 invariants extracted; 10 HELD, 1 VIOLATED, 1 CONDITIONAL.
- The VIOLATED invariant independently rediscovered iteration 11's single
  most severe confirmed finding (the unauthenticated `getDownloadFileSignedURL`)
  via a completely different reasoning path — the second independent trial
  (after iteration 6's) showing this technique's candidates converge with
  domain-based Hunt's on real bugs rather than being unrelated noise.
- The CONDITIONAL invariant found something iteration 11's `security` domain
  had missed entirely (Stripe customer lookup-by-email silently reusing a
  pre-existing customer, crossing billing history under narrow preconditions)
  — independently Verified as CONFIRMED, real but low-to-medium severity. This
  is the first concrete "found something domain-based hunting missed" result,
  not just convergence on what domain-based hunting already would have found.
- Both non-HELD classifications confirmed real on independent adversarial
  Verify (0 false positives this trial, `n=2` — real progress on, not closure
  of, the false-positive-rate gap).
- Cost: ≈190K tokens total (extract+check ≈120K, verifying the one new claim
  ≈70K) — for comparison, iteration 11's `security` domain alone (Hunt+Verify,
  Deep depth, same project) cost ≈213K tokens. Comparable cost to that one
  domain's own existing process, for independently reconfirming its top
  finding plus one it missed.
- A real limitation, not just a caveat: despite reading all three payment
  webhook handlers in full (the exact code with iteration 11's confirmed
  missing-idempotency bug), the extraction pass never produced an invariant
  about duplicate/retried input — it caught the repeated
  signature-verification pattern across the three files but not the also-
  repeated missing-idempotency pattern in the same files. The technique has a
  real attention bias toward whichever structural pattern happens to catch
  it, not uniform coverage of everything it reads.

**Decision**: promoted from "purely experimental, don't invoke" to a
**validated opt-in enhancement** — worth reaching for on the `security`
domain at Standard/Deep depth specifically, still not promoted to a default
`SKILL.md` step-1 stage for every run/domain (both trials so far are scoped to
auth/access-control-shaped invariants; correctness/reliability/data-integrity-
shaped invariant extraction, and behavior at obs-studio-scale, remain
untested). Reference file renamed from `EXPERIMENTAL-invariant-extraction.md`
to `invariant-extraction.md` to match the status change; `README.md` updated
to match.

## Iteration 13 — invariant extraction, trial 3 (directed prompt closes the attention-bias gap)

Direct follow-up to iteration 12's own limitation: a generic extraction prompt
had missed a missing-idempotency bug despite reading the exact vulnerable
code. Re-ran against the same project's `payment/` subsystem (no prior
knowledge, as always), this time with the extraction prompt explicitly aimed
at "duplicate input / state transition / derived-value consistency"
invariants instead of a generic ask.

**Result: this closed the gap.** The redirected prompt found the missing
webhook-idempotency issue directly — the same mechanism/severity iteration
11's `data-integrity` domain had independently confirmed, but this time
*found* by the invariant pass itself, not merely convergent with something
else. It also surfaced two genuinely new issues: LemonSqueezy's webhook
stamps `datePaid` at processing time while Stripe/Polar derive it from the
event's own timestamp (a real correctness inconsistency no prior pass on this
project had caught), and a TOCTOU race in Stripe customer creation under
concurrent checkout requests. Full write-up in
`adaptive-audit-execute/references/invariant-extraction.md` ("Trial 3").

**Conclusion drawn**: the attention bias iteration 12 surfaced is addressable
by prompt design (running a differently-lensed extraction pass), not an
inherent ceiling on the technique — but that in turn means invocation should
run more than one lens (at minimum authorization/ownership, and
duplicate-input/state-transition) rather than assume one generic pass covers
everything, since trial 2 and trial 3's lenses surfaced materially different,
non-overlapping findings from related code.

## Iteration 14 — invariant extraction, trial 4 (first test at large-C-codebase scale)

The other open gap from iteration 12: no data on how the technique behaves on
a codebase large and unfamiliar enough that a single read-through can't cover
it. Run against `obsproject/obs-studio`'s `plugins/obs-outputs/`
(~20,571 lines of C) — the same real-world target as iteration 9's full
7-domain audit — again with no knowledge of that audit's findings.

Coverage was disclosed honestly rather than glossed over: only ~20% of the
codebase was read closely, with entire subsystems (two codec-specific
bitstream parsers, ~1,500 lines) never opened at all. Within that partial
coverage: **the technique independently rediscovered iteration 9's two most
severe confirmed findings** (third independent convergence trial, and the
first on a large, unfamiliar, memory-unsafe C codebase rather than
TypeScript/Python) — **and found two additional real, independently-Verified
issues iteration 9's own `security` Hunt had not surfaced**, sitting in code
a different domain (`architecture`) had read for an unrelated lens, or that
no domain's Hunt had examined at all. In aggregate severity, both are at
least comparable to, and one is more severe than, anything iteration 9 found
in this subsystem.

**Redacted for the same reason as iteration 9**: full technical detail is not
published here. Both new findings are independently Verified and have been
folded into the private disclosure draft prepared for OBS's official
security contact, with the more severe one promoted to the top of that
draft.

**The self-honesty check produced a genuinely useful internal signal, not
just a caveat**: the two invariants the extraction agent itself flagged as
least concretely grounded (closer to generic hygiene phrased in
codebase-specific language than tied to a verified repeated pattern) going
into the checking pass turned out to be exactly the two that were violated
worst. Weakly-grounded invariants correlating with where real gaps are is
itself a signal worth designing around in future runs (e.g., treat
low-grounding invariants as a prioritization cue for where to look hardest,
not just a confidence caveat to report).

**What this changes about the technique's standing**: this is the single
most consequential result across all four trials to date — real,
more-severe-than-previously-known findings in a widely-deployed real
project, found specifically because the technique isn't scoped by domain the
way Hunt is. A function one domain's Hunt read for one lens and another
domain's Hunt never re-read for a different lens fell into exactly the gap
between domain boundaries that a domain-agnostic invariant pass doesn't have.
This does not mean the technique scales cleanly to large codebases — only
~20% was covered — but it means even partial, time-boxed coverage at that
scale still finds real, high-value things, which is the more defensible and
more interesting claim. Full standing assessment, and the resulting
invocation guidance (run multiple lenses; require honest coverage
disclosure on large codebases), recorded in
`adaptive-audit-execute/references/invariant-extraction.md`.

## Iteration 15 — closing engineering gaps from a self-assessment, not a validation run

Following an honest self-assessment of the project (weaknesses: audit cost,
small real-world sample, invariant-extraction lens coverage, degraded
same-session fallback quality, no automated regression protection, and the
obs-studio safety-filter interruption), three of the six weaknesses were
addressed directly; the other three (a diff/incremental audit mode, growing
the real-world sample, and using a child session for genuine subagent
isolation) were deliberately left as open design questions rather than
implemented under a vague mandate — each is a real architectural change with
its own cost/tradeoff that deserves its own decision, not something to slip
in silently.

**Automated regression tests for `receipts.py`** (`tests/test_receipts.py`,
run via `.github/workflows/test.yml`): 15 tests covering both skill folders'
copies of the script — fingerprinting, write/list roundtrip,
`write-result`'s rejection of an unknown `plan_id`, `export-csv`/`report`
consistency with `debt`, and, most importantly, two regression tests
directly protecting the iteration-10 `depth_executed` fix: a result recorded
with `depth_executed: "quick"` under a plan that specified `"deep"` must
report `max_verified_depth_ever == "quick"`, while an old-style result with
no `depth_executed` field at all must still fall back to the plan's depth.
A `test_scripts_stay_identical` check also guards against the two skill
folders' copies of `receipts.py` silently drifting apart, which nothing
previously checked for. This is the one part of the project that's pure,
deterministic logic rather than LLM output — CI can protect it the way it
can't protect `SKILL.md` behavior itself, which still depends on hand-run
evals.

**Explicit recovery instruction for the safety-filter interruption**
(`adaptive-audit-execute/SKILL.md`, security Verify section): iteration 9
already fixed the *prevention* side (lead with static tracing, not a rebuilt
harness) but had no instruction for what to do if a filter interruption
happens anyway. Added: dispatch a fresh Verify subagent with the
static-first instruction rather than resuming the interrupted approach,
rather than leaving that recovery step to be improvised in the moment.

**Multi-lens invariant-extraction guidance**: already addressed by trial 3's
own conclusion and the "How to invoke it" section in
`adaptive-audit-execute/references/invariant-extraction.md` (run more than
one explicit lens, not one generic pass) — reviewed during this pass and
confirmed no further change was needed here; this weakness was already
closed by prior work, not newly fixed now.

## Iteration 16 — diff-scoped re-audit (addressing the cost weakness directly)

Direct follow-up to the cost weakness left open in iteration 15: the project
always re-examines a whole project every run, even when almost nothing has
changed since the last full audit. Added `adaptive-audit-plan` step 0.5: for
a project with git history and a prior full-scope audit recorded, if the
diff since that audit's commit is clearly small (≤15% of tracked files and
≤20 files absolute), the plan step **asks the person to choose** between a
cheap diff-only re-audit (scoped to the changed files and their direct blast
radius) and a full re-audit — surfacing which domains currently carry real
accumulated debt that a diff-only pass would leave untouched, rather than
silently picking one or the other. This design (ask, don't decide, when the
choice is real; show the debt cost of the cheap option) came directly out of
a conversation about how to close this specific weakness, not from an
eval run — worth naming as its origin.

**Why a choice, not an automatic decision**: a diff-only pass isn't strictly
better than a full one — it's cheaper but structurally blind to anything
outside the diff, including whatever a domain's existing accumulated debt
already represents. Automatically defaulting to diff-mode whenever it
qualifies would quietly let real debt accumulate indefinitely on any project
that only ever gets small incremental changes between audits. Automatically
defaulting to full mode whenever a smaller option exists defeats the point
of adding it. Neither default is honestly always right, so the plan asks
instead of picking — the same principle as this project's existing
dry-run/read-only handling (a real constraint the skill honors rather than
silently overriding).

**`receipts.py` changes, tested**: a `"diff"`-scoped plan's execution results
must not count as verifying the whole domain the way a `"full"`-scoped
result does — `_compute_debt` now reads `scope` from the *plan* a result
executed (not the result itself, since execution can't widen or narrow what
the plan already decided), and diff-scoped results are tracked separately as
`diff_checks_since_last_full` rather than advancing `times_executed`/
`max_verified_depth_ever`. `report`'s table gained a `DIFF SINCE FULL`
column and `export-csv` a matching field. 4 new pytest tests cover: a
diff-scoped result doesn't count as full verification; a full-scope result
after one or more diff-scoped ones resets the counter and records real
verification; both existing behaviors were exercised end-to-end via the
actual CLI (subprocess calls), not just the internal `_compute_debt`
function directly.

**A real latent bug found and fixed while writing these tests, not before**:
the first version of the reset test failed because `_load_all`'s sort falls
back to glob (content-hash) order whenever two records tie on `created_at`,
and `created_at` was only second-resolution — two results written by the
same script invocation or a fast automated run can easily land in the same
wall-clock second, at which point their relative order in every debt
calculation becomes arbitrary rather than reflecting when they were actually
written. This is not a new bug introduced by diff-scoping; it's a
pre-existing property of the timestamp format that the new tests were simply
the first to be sensitive enough to expose (nothing before this needed
sub-second ordering to tell two records apart). Fixed by switching
`created_at` to microsecond-precision ISO-8601 timestamps
(`_now_iso()`); both `receipts.py` copies re-synced, all 19 tests (15 from
iteration 15, 4 new) pass on both.

**Not yet validated**: this has only been exercised through `receipts.py`'s
own logic (verified deterministically) and the CLI directly — no real agent
run has yet gone through `adaptive-audit-plan` step 0.5's own judgment (git
diff sizing, presenting the choice via `AskUserQuestion`, correctly scoping
a diff-mode Hunt to blast radius rather than the whole project). That's the
next real-world validation gap for this feature, the same way staged
depth-escalation (iteration 10) wasn't validated on a real project until
iteration 11.

## Addendum to iteration 16 — freshness check (step 0.4), same conversation

A follow-up question in the same conversation surfaced a real gap the diff
feature had introduced without addressing it: step 0.5's diff sizing (and
every other step's project inspection) silently assumes the local checkout
is current. A local clone behind its remote breaks that assumption
invisibly — the plan would be built against stale code, and step 0.5's diff
size could be measured against the wrong commit entirely.

Added `adaptive-audit-plan` step 0.4, ahead of step 0.5: `git fetch` (never
`git pull` — this skill's read-only guarantee is about the target project's
own files, and `git pull` would touch the working tree) to update
remote-tracking refs, then compare local `HEAD` against them. If local HEAD
is behind, say so prominently in the output and ask the person whether to
proceed against the stale checkout or pull first and re-run, rather than
silently doing either. In dry-run mode, even `git fetch` is skipped (it
writes inside the target repo's own `.git/` directory — remote-tracking
refs, `FETCH_HEAD` — which is a real side effect even though it never
touches a tracked file), falling back to whatever remote-tracking state
already exists locally and disclosing that freshness couldn't be actively
verified this run.

Documentation-only change (no `receipts.py` logic involved) — not yet
validated against a real project either, same open gap as the rest of
iteration 16.

## Iteration 17 — explicit opt-in to save the findings report into the project

Another follow-up in the same conversation: for the person's own project (as
opposed to the third-party targets this project's own validation history is
built on), it's reasonable to want the findings report kept with the project
rather than only surfaced in chat. Added to `adaptive-audit-execute` only
(not `adaptive-audit-plan` — a plan-only run's output is less clearly worth
persisting the same way a findings report is, so this stayed scoped to where
the actual use case is): step 0 now also detects an explicit request to save
the report into the project, and step 4.5 (new) writes it to
`docs/audit-reports/<date>-<slug>.md` when that request was present.

**Deliberately not auto-detected from repo ownership.** Checking whether a
target repo is "the person's own" (matching a git remote's owner against
some notion of the current user) was considered and rejected: this skill's
"never writes to the audited project" guarantee is part of what its own
real-world validation runs against third-party projects (obs-studio,
open-saas, yamaha-rcp-osc-bridge) rely on for trust, and a misclassification
here — writing into a repo that isn't actually the requester's to write
into — would be a real, hard-to-undo mistake with no clean recovery. An
explicit per-request signal (the same pattern already used for dry-run mode
and the freshness check) has no such failure mode: worst case, the option
just doesn't trigger when it could have.

**Committing is explicitly left to the person, never done by the skill.**
Writing the file is what was asked for; `git add`/`git commit` is a separate,
visible action affecting the project's own history, which this project's
broader operating conventions already treat as something requiring a human
decision, not something a skill should do on someone's behalf just because
adjacent behavior was authorized.

**Security-content permanence is called out explicitly, not left implicit.**
A report containing a real, currently-unpatched vulnerability description
becomes part of git's permanent history the moment it's committed —
recoverable forever unless history itself is rewritten, even after the
underlying code is fixed. Step 4.5 requires surfacing this in the chat
response itself (not just as a line inside the written file, which is easy
to miss) whenever the report being saved contains a CONFIRMED/PLAUSIBLE
security finding or another medium/high-severity unpatched issue, so the
person has that information before deciding whether to commit, not after.

`receipts.py`'s own records (plan receipts, execution results) are
unaffected and stay external regardless of this setting — they're
operational debt-tracking data, not the human-readable deliverable this
feature is about, and mixing the two was rejected on that basis alone.

Documentation-only change — not yet validated against a real project.

## Iteration 18 — self-hosted plugin marketplace, closing the actual gap the version-bookkeeping addition (iteration 16-17-adjacent) didn't

Iteration 17's `VERSION`/`CHANGELOG.md`/`release.yml` addition was explicit
that it gave this project's own history a stable marker, nothing more — it
did not, and could not, make an installed copy of these skills actually
update. A follow-up question in the same conversation surfaced that this
wasn't what was actually wanted: the person wanted their own installed
copy to pick up new versions without a manual re-copy.

Before implementing, three separate facts were verified against official
Claude Code documentation (not assumed) via the `claude-code-guide` agent,
since getting any of them wrong would have meant recommending a change
that silently doesn't do what it claims to:

1. Whether a plugin-sourced skill still gets automatically model-invoked
   by its `description` field the same way a plain `.claude/skills/` one
   does, or whether plugin packaging forces explicit `/plugin-name:skill`
   invocation only. **Confirmed**: automatic invocation is preserved;
   namespacing only affects the manual slash-command alias. This was the
   one fact that mattered most — this project's founding premise is that a
   bare "バグチェックして" triggers the skill with no explicit command, and
   a change that silently broke that would have been a real regression.
2. Whether a single repo can self-host both a marketplace and the one
   plugin it lists (rather than needing a separate marketplace repo), and
   whether the existing top-level `adaptive-audit-plan/`/
   `adaptive-audit-execute/` folders could stay exactly where they are.
   **Confirmed**: yes to both — a `skills` array field in the marketplace
   entry can point at arbitrary paths relative to the plugin root, so no
   file moves were needed.
3. Whether adding `.claude-plugin/` breaks or coexists with the existing
   plain-copy `.claude/skills/` install method documented in the README.
   **Confirmed**: they coexist untouched (different namespaces).

Added `.claude-plugin/marketplace.json` (one file, no restructuring):
declares one plugin (`adaptive-audit`) whose `skills` field points at both
existing folders. README's "Usage" section now documents both install
paths side by side (plain copy: no update mechanism, vs. plugin: `/plugin
marketplace add` + `/plugin install`, later `/plugin marketplace update` to
pull the latest, with the honest caveat that auto-update itself is off by
default for a third-party/personal marketplace like this one and has to be
enabled per-marketplace if a fully hands-off flow is wanted).

**Guardrail added, not just a feature**: `marketplace.json`'s plugin
`version` field and the root `VERSION` file are two files a human now has
to remember to bump together, with nothing enforcing that at write time —
exactly the kind of drift `test_scripts_stay_identical` already guards
against for the two `receipts.py` copies. Added
`tests/test_versioning.py` (2 new tests: version fields match; the
`skills` paths in `marketplace.json` actually exist and match the expected
set) — 21 tests total now, up from 19.

CHANGELOG.md's own header, which iteration 17 had written to say
marketplace distribution "was deliberately not pursued," was corrected in
the same change — it's no longer accurate as a blanket statement now that
a personal/third-party marketplace exists; only *public* marketplace
listing (npm/PyPI-style broad distribution) remains the thing that wasn't
pursued, and the header now says so precisely instead of overclaiming in
either direction.

Not yet validated end-to-end against a real Claude Code session (adding
the marketplace, installing from it, confirming auto-invocation actually
fires post-install, running `/plugin marketplace update` after a new
commit) — the facts above are verified against documentation, not by
actually exercising the install flow in this project's own validation
history yet.
