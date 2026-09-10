# Audit Domain Taxonomy

Fixed set of 11 domains. Keep this list stable across runs — adding an ad-hoc
12th domain for one project breaks comparability with past/future audit plans.
If a project genuinely needs something not covered here, note it as a caveat in
the plan rather than silently inventing a new domain name.

For each domain: what project signals raise its score, what request wording maps
to it (not exhaustive — use judgment for paraphrases and other languages), and
what Quick/Standard/Deep mean specifically for that domain.

---

## security

**Raises score when found**: authentication/session/token handling, password or
credential storage, payment/billing code, PII fields, file upload handling,
deserialization of untrusted input, raw SQL string concatenation, subprocess/exec/
eval calls, cryptography usage, CORS/CSP config, public network-facing endpoints.

**Request wording**: security, セキュリティ, 脆弱性, vulnerability, exploit, pentest,
攻撃.

**Blast-radius floor**: if auth, payment, or PII signals are present, this domain
gets a floor score even with zero explicit mention — see SKILL.md step 3.

- Quick: scan for the obvious classes above via grep/pattern match, no exploitation attempt.
- Standard: trace at least one plausible attack path per class found to a concrete file/line.
- Deep: attempt reproduction/PoC where safely possible in a sandboxed way, check dependency CVEs.

## correctness

**Raises score when found**: any project (this is close to a universal baseline) —
weight up further for complex branching logic, numeric/date handling, state
machines, parsers.

**Request wording**: bug, バグ, 正しく動くか, correctness, logic error, edge case.

- Quick: read for obvious logic errors, off-by-one, null/undefined handling in changed code.
- Standard: trace key business-logic paths against their intended behavior (docs, tests, or inferred intent).
- Deep: enumerate edge cases per function/endpoint and check each is handled.

## performance

**Raises score when found**: loops over I/O or DB calls (N+1 patterns), large
in-memory data structures, synchronous blocking calls in a request path, missing
indexes implied by query patterns, frontend re-render-heavy code, hot paths
identified by naming (`process*`, `batch*`) or by size.

**Request wording**: performance, パフォーマンス, 遅い, slow, 重い, optimize, latency.

- Quick: flag obvious anti-patterns (N+1, nested loops over large collections) by inspection.
- Standard: reason about algorithmic complexity of the hot paths found, note the ones that need profiling.
- Deep: identify candidate benchmarks/profiling points and, if a runtime is available, run them.

## reliability

**Raises score when found**: external calls without timeout/retry, missing error
handling around I/O, background jobs/queues without dead-letter or retry logic,
places `panic!`/uncaught exceptions can propagate, startup/shutdown handling.

**Request wording**: reliability, 落ちる, crash, error handling, 障害, 安定性, robustness.

- Quick: check that external calls and I/O have some error handling at all.
- Standard: trace failure propagation for the top few external dependencies.
- Deep: consider partial-failure and retry-storm scenarios, check idempotency of retried operations.

## architecture

**Raises score when found**: large files/functions, circular imports, business
logic embedded in framework/controller layers, duplicated logic across modules,
unclear module boundaries.

**Request wording**: architecture, 設計, 構成, maintainability, 保守性, technical debt,
refactor.

- Quick: note obvious god-files/god-functions and layering violations by inspection.
- Standard: map the actual dependency graph for the touched area vs. the intended one.
- Deep: propose a concrete restructuring and check it against existing tests/usages.

## data-integrity

**Raises score when found**: database migrations, schema definitions, places
without input validation before persistence, multi-step operations without
transactions, denormalized data updated in more than one place.

**Request wording**: data integrity, データ整合性, 不整合, consistency, migration.

- Quick: check validation exists at persistence boundaries.
- Standard: trace multi-step writes for missing transactional guarantees.
- Deep: check migrations for reversibility and for behavior under partial application.

## concurrency

**Raises score when found**: goroutines/threads/async tasks, shared mutable
state, locks/mutexes/semaphores, queue consumers, in-memory caches written from
multiple places.

**Request wording**: concurrency, 並行, race condition, デッドロック, deadlock, thread-safe.

- Quick: flag shared mutable state touched from more than one concurrent path.
- Standard: trace lock ordering/usage around the flagged state for obvious races/deadlocks.
- Deep: reason about interleavings explicitly, or run a race detector if the toolchain has one.

## dependency-health

**Raises score when found**: lockfiles present, especially if stale (compare
manifest last-modified vs. lockfile), direct use of packages known for frequent
CVEs, unpinned versions, vendored/copy-pasted third-party code.

**Request wording**: dependency, 依存, supply chain, outdated, vulnerable package.

- Quick: list direct dependencies with obviously ancient pinned versions.
- Standard: cross-reference dependencies against known-CVE databases if reachable, else flag as unverified.
- Deep: check transitive dependency tree, license compatibility, and vendoring integrity.

## configuration-deployment

**Raises score when found**: `.env`/config files, CI/CD pipeline definitions,
infrastructure-as-code, secrets referenced by name in code, environment-specific
branching logic.

**Request wording**: config, 設定, デプロイ, deployment, CI/CD, infra, 本番.

- Quick: check no secrets are hardcoded or committed in plaintext.
- Standard: check config validation/defaults are safe for a misconfigured environment.
- Deep: trace the full deploy pipeline for a single point of failure or missing rollback path.

## test-coverage

**Raises score when found**: any project with a test directory or test framework
config; weight up further for critical paths (payment, auth, data writes) with no
matching test file.

**Request wording**: test coverage, テストカバレッジ, テスト, untested, test gap.

- Quick: check whether the highest-risk modules found in other domains have any test file at all.
- Standard: check whether existing tests actually exercise failure/edge paths, not just the happy path.
- Deep: identify concretely which untested branches matter most and why.

## observability

**Raises score when found**: background jobs, async workers, external API
integrations, anything already flagged under reliability — these are the places
where "did it actually work?" needs a signal, and often don't emit one.

**Request wording**: observability, 監視, logging, ログ, metrics, alerting, 可観測性.

- Quick: check that failure paths in reliability-flagged code emit at least a log line.
- Standard: check whether critical operations have a way to confirm success after the fact (metric, log, status field).
- Deep: identify what an on-call person would need to diagnose a failure here, and check if it exists.
