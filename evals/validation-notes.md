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

## Next validation round (not yet run)

- A case with genuinely no elevated-risk signal anywhere (does it correctly
  produce a short, low-domain-count plan instead of padding it out?).
- A case where the request explicitly asks to skip a domain the project clearly
  needs (does the skill respect an explicit exclusion, or override it the same
  way it overrides silence?).
- A longer history (5+ runs) with a domain that keeps sitting just under the
  "worth mentioning" bar — does accumulated debt eventually flip it to selected,
  or does the bump prove too weak in practice to ever matter?
