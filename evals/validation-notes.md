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
