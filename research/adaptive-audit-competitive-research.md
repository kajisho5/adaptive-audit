# Adaptive Audit Engine — 競合調査・差別化検証レポート

- 調査日: 2026-09-10
- 対象: Claude Code Skillとして企画中の「Adaptive Audit Engine（仮）」
- 目的: 実装前に、既存Skill/OSSリポジトリ/Claude Code公式機能との重複を検証し、差別化可能性を判定する
- 調査方法: WebSearch/WebFetchによる実リポジトリの確認（README/SKILL.md/実装ファイルまで確認。README記載のみで判断した箇所は明示）

> **前提の確認**: 本ドキュメントは実装仕様書ではなく、実装前の競合・新規性・成立可能性の検証結果である。

---

## 0. エグゼクティブサマリー（結論を先に）

- **判定: CONDITIONAL GO**（差別化要素はあるが範囲が狭く、スコープを絞り込む必要がある）
- 「複数観点の自然言語トリガー」「Multi-agent」「Adversarial verification（Skeptic/Referee型）」「Evidence-based」「Audit-the-audit（監査計画自体の再検証）」は**すべて既存OSSで実装済み**。特に以下2件は差別化検証時に最優先で参照すべき直接競合：
  - **cloudflare/security-audit-skill**（★3.3k）— Recon→Hunt→Validate→Report→構造化出力→独立検証の6フェーズ、プロジェクト種別に応じたルーティング、ラン間の重複排除、フルの監査履歴を実装済み。
  - **dinosn/raptor-loop-hunt**（★217）— 網羅性を強制するコンポーネント台帳、エンゲージメント横断の永続KB、監査計画自体を機械的に検証する「Closure Gate」を実装済み。
- **本当に空いている差別化領域は2つだけ**：
  1. **監査領域をセキュリティ/バグに限定しない、ドメイン非依存の適応的Audit Plan生成**（既存はほぼ全てセキュリティ/バグ特化）
  2. **監査タイプを横断した永続的Coverage/Audit-Debt管理**（既存は単一監査系統内の履歴管理に留まる）
- 「Invariant抽出」（仮説B/C）は最も新規性が高い一方、実証済み実装は事実上存在しない（`dystopiaxyz/hound-audit-ai`が唯一の試みだが★0・未使用）。**最もリスクが高く、最も差別化になり得る要素**。
- 命名: `adaptive-audit`（リポジトリ名）はGitHub上で第三者との衝突なし（唯一の同名リポジトリは調査対象自身）。ただし「adaptive」「audit」「engine」という単語自体は差別化要素にならないため、Skill名は最終スコープ確定後に見直しを推奨（詳細は§9）。

---

## 1. Competitive Landscape（競合一覧）

### 1.1 GitHub検索で確認した競合（実在確認済み・22件+）

| # | Repo | Stars(概算) | 主目的 |
|---|---|---:|---|
| 1 | elementalsouls/Claude-BugHunter | ~4.4k | 83 Skill/自然言語での自動起動/recon→hunt→validate→report→evidenceのバグバウンティ向けフルパイプライン |
| 2 | danpeg/bug-hunt | ~145 | Hunter/Skeptic/Refereeの3独立エージェントによる敵対的バグハント |
| 3 | codexstar69/bug-hunter | ~505 | 上と酷似したHunter/Skeptic/Referee構成、STRIDE脅威モデル+CVE依存関係スキャン付き（#2との関係は未確認だが用語がほぼ同一） |
| 4 | wrsmith108/claude-skill-security-auditor | ~33 | npm audit ラッパー、重篤度別の是正レポート |
| 5 | **trailofbits/skills** | **~7k** | Trail of Bits公式マーケットプレイス。監査13種+検証（property-based testing/mutation testing/spec-to-code）等50 Skill |
| 6 | awesome-skills/code-review-skill | ~1.9k | 20言語対応、4フェーズ、6段階重篤度 |
| 7 | levnikolaevich/claude-code-skills | ~559 | 「証跡か明示的な非該当理由」を全チェック項目に要求する評価軸。動的スコープの思想が明確 |
| 8 | anthroos/claude-code-review-skill | ~40 | 280+チェック、単一エージェント逐次型 |
| 9 | wan-huiyan/agent-review-panel | ~35 | 4-6人格レビュアーが16フェーズで討論、ドメイン自動判定でペルソナ選定、根拠検証+確信度ラベル |
| 10 | addyosmani/adverse | ~56 | Auditor/Adversary/Pragmatistの3人格による相互尋問+決定論的統合 |
| 11 | alecnielsen/adversarial-review | ~39 | Claude+GPT Codexの討論ループ、停滞検知のサーキットブレーカー |
| 12 | alanchn31/multi-agent-code-review | ~6 | LangGraphでファイル種別に応じ専門エージェントを動的選択 |
| 13 | **cloudflare/security-audit-skill** | **~3.3k** | 公式「Project Glasswing」手法。6フェーズ、プロジェクト種別ルーティング、ラン間重複排除、独立再検証 |
| 14 | evilsocket/audit | ~852 | Glasswing手法の明示的な再実装。8段階、段階別モデル切替 |
| 15 | sari3l/security-code-audit-skill | ~3 | `.security-code-audit-state/`で永続化、リグレッションモードで既知findingを再検証 |
| 16 | dystopiaxyz/hound-audit-ai | 0 | ビジネスロジック↔コードの「aspect graph」構築、仮説/invariant/観察を反復蓄積。研究段階・未使用 |
| 17 | PurCL/RepoAudit（ICML2025） | ~440 | リポジトリ全体の自律バグ検出（NPD/メモリリーク/UAF等）、構文+データフロー2種のエージェント |
| 18 | heavy3-ai/code-audit | ~45 | 複数モデル合議制（correctness/performance/securityの3専門レビュアー） |
| 19 | HeadyZhang/agent-audit | ~227 | エージェント自体の静的セキュリティ監査（OWASP Agentic Top 10準拠、SARIF出力） |
| 20 | scadastrangelove/agent-audit | ~15 | 同名だが別物。エージェントのセッションログ/設定のフォレンジック監査 |
| 21 | TheMorpheus407/RepoLens | ~297 | 280+専門エージェント、34ドメイン、13モード。README自身が「サンドボックス化されていない」と明記 |
| 22 | dinosn/raptor-loop-hunt | ~217 | 上記1.0参照 |

### 1.2 事前指定候補11件の実装詳細確認（README止まりでなくSKILL.md/実装まで確認）

| Repo | Stars | NL Trigger | Multi-Agent | Adaptive | Audit Plan | Invariant | Evidence | Runtime Verify | Coverage | History | Audit-the-Audit |
|---|---:|---|---|---|---|---|---|---|---|---|---|
| danpeg/bug-hunt | 145 | Full | Full | None | None | None | Full | None | None | None | Partial |
| tripinfinite-gif/claude-skill-phase-review | 2 | Full | Full | Full | Full | None | Partial | None | None | None | Partial |
| Mixosss/code-audit-skill | 2 | Full | **Adjacent**※ | Partial | Partial | None | Full | Partial | None | None | None |
| **cloudflare/security-audit-skill** | 3.3k | Full | Full | Full | Full | Adjacent | Full | Full | Full | Full | **Full** |
| escoffier-labs/skillet | 4 | Full | **None**※ | Partial | None | None | Full | None | Partial | Adjacent | None |
| **dinosn/raptor-loop-hunt** | 217 | Full | Partial | Full | Full | Adjacent | Full | Partial | **Full** | **Full** | **Full** |
| schatt93/universal-audit-skill | 0 | Partial | Conceptual-only | Full※spec | Full※spec | None | Full※spec | Conceptual-only | Full※spec | Full※spec | Full※spec |
| fkguo/nullius (review-swarm) | 16 | Adjacent | Full | Adjacent | None | None | Full | Full | Partial | None | Partial |
| craigkitterman/cross-model-code-review-skill | 4 | Full | Full | Full | Partial | None | Full | None | Partial | None | Partial |
| Dimillian/Skills (review/bug-hunt-swarm) | ~4k | Full | Full | Partial | None | None | Full | None | None | None | None |
| anthroos/claude-code-review-skill | 40 | Full | None | Partial | None | None | Partial | None | None | None | None |

※ **Mixosss**: READMEは「Orchestrator/Mapper/Verifier/Boundary Tester/Reporter」の5役割を謳うが、実プロンプトを確認すると単一エージェントの逐次思考であり、Task-tool委譲は行われていない（README記載と実装の乖離例）。
※ **skillet**: 個別スキル（security-sweep等）は単発プロンプト型で、マーケ文言の「複数skill連携」は確認できず。
※ **schatt93**: 大規模な仕様書（v10.1、単一Markdown）であり、`adapters/`等は設計意図の記述のみで動作実装は未確認。★0。「Full」評価は全て「仕様上は」の意味であり、動作実証なし。

### 1.3 Claude Code公式機能がすでにカバーしている範囲

Anthropic公式ドキュメントで確認：

- **Managed Code Review**（[code.claude.com/docs/en/code-review](https://code.claude.com/docs/en/code-review)）— PR毎に専門エージェント群が実行され、実際のコード挙動と突き合わせる検証ステップでFalse Positiveを除去、重複排除+重篤度付けまで標準機能。`REVIEW.md`でスコープ・重篤度基準・再レビュー収束条件をプロジェクト単位でカスタマイズ可能。
- **`/code-review`コマンド** — 診断の深さを `low → max` のeffort levelで切替可能（＝適応的深度は既にプラットフォーム機能）。`ultra`でクラウドのより深いレビューに昇格。
- **Subagents / Agent Teams / Hooks / Skills marketplace / GitHub Action** — サードパーティAudit Skillの大半（Hunter/Skeptic/Refereeパターン含む）はこれらの上に構築されている基盤機能であり、それ自体は競合ではなく前提インフラ。

**含意**: 「動的に監査深度を決める」「Evidence検証」「重複排除」は既にAnthropic自身が製品レベルで提供している。これらを差別化点として主張することはできない。

---

## 2. Feature Matrix（40項目）

「市場飽和度」は確認できた実装の広がりを示す（Saturated=多数実装済み／Common=複数実装あり／Rare=1-2件のみ確認／Novel=実証済み実装が見つからない）。

### 基本（1-10）

| # | 機能 | 市場飽和度 | 最有力の既存実装 |
|---|---|---|---|
| 1 | Natural language trigger | Saturated | ほぼ全Skill共通 |
| 2 | Whole-project scan | Common | cloudflare, universal-audit-skill, RepoAudit |
| 3 | Git diff scan | Common | Anthropic `/code-review`, tripinfinite-gif |
| 4 | Multi-agent | Common | danpeg/bug-hunt, cloudflare, Dimillian/Skills |
| 5 | Specialized reviewers | Common | heavy3-ai council mode, Anthropic managed review |
| 6 | Adversarial reviewer | Common | danpeg Skeptic, addyosmani/adverse, cloudflare Validate |
| 7 | Multi-model | Rare | craigkitterman, fkguo/nullius, heavy3-ai |
| 8 | Confidence score | Common | anthroos(≥70), wan-huiyan(epistemic-confidence) |
| 9 | Severity | Saturated | ほぼ全Skill共通 |
| 10 | Finding deduplication | Common | Anthropic managed review, cloudflare, sari3l |

### Adaptive（11-17）

| # | 機能 | 市場飽和度 | 最有力の既存実装 |
|---|---|---|---|
| 11 | Project type detection | Common | cloudflare recon phase, tripinfinite-gif |
| 12 | Architecture detection | Rare | cloudflare（architecture.md生成） |
| 13 | Risk detection | Common | tripinfinite-gif（sensitive-bump）, cloudflare |
| 14 | Dynamic audit depth | Common | **Anthropic公式 `/code-review` effort levels**, tripinfinite-gif S/M/L |
| 15 | Dynamic reviewer selection | Common | wan-huiyan, alanchn31 |
| 16 | Dynamic test strategy | **Novel/Rare** | 明確な実装未確認（ギャップ候補） |
| 17 | Dynamic audit plan | Common | cloudflare, tripinfinite-gif, schatt93(spec) |

### Evidence（18-25）

| # | 機能 | 市場飽和度 | 最有力の既存実装 |
|---|---|---|---|
| 18 | Source evidence | Saturated | ほぼ全Skill共通（git blame等） |
| 19 | Static analysis evidence | Common | Mixosss, agent-audit(SARIF) |
| 20 | Runtime evidence | Rare | cloudflare（fuzzing/harness）, dinosn(PoC必須) |
| 21 | Reproduction | Rare | cloudflare, dinosn |
| 22 | Test evidence | **Novel/Rare** | 明確な実装未確認（テストスイート実行を証跡として統合する例が乏しい） |
| 23 | External tool evidence | Common | Burp MCP, npm audit, SARIF, CVEスキャン |
| 24 | Finding verification | Common | cloudflare Validate, danpeg Skeptic |
| 25 | Independent verification | Common | cloudflare Phase6, dinosn Closure Gate |

### Coverage（26-30）

| # | 機能 | 市場飽和度 | 最有力の既存実装 |
|---|---|---|---|
| 26 | Audit coverage | Rare | **dinosn**（コンポーネント台帳+TRIED.md） |
| 27 | Unverified area reporting | Rare | dinosn(UNCOVERED状態), schatt93(spec) |
| 28 | Assumption tracking | **Novel/Rare** | 明示的な「仮定ログ」実装は未確認 |
| 29 | Missing evidence reporting | Rare | **levnikolaevich**（証跡 or 明示的非該当理由を必須化） |
| 30 | Audit completeness assessment | Rare | dinosn Closure Gate(PASS/PARTIAL/FAIL) |

### Stateful（31-36）

| # | 機能 | 市場飽和度 | 最有力の既存実装 |
|---|---|---|---|
| 31 | Finding fingerprint | Common | cloudflare findings.json, sari3l |
| 32 | Historical findings | Common | cloudflare run-N, dinosn kb/, sari3l |
| 33 | Regression of findings | Rare | **sari3l**（是正後の再検証モード） |
| 34 | Previous audit comparison | Rare | cloudflare（累積ラン）, sari3l |
| 35 | Unexplored-area prioritization | **Novel/Rare** | dinosn kb/が最も近いが「次回優先度付け」の明示実装は未確認 |
| 36 | Change-aware re-audit | Rare | tripinfinite-gif, Anthropic `/code-review`(diff) |

### Meta（37-40）

| # | 機能 | 市場飽和度 | 最有力の既存実装 |
|---|---|---|---|
| 37 | Audit-plan verification（計画自体への攻撃） | **Novel/Rare** | schatt93がspec上で言及するのみ。動作実装は未確認 |
| 38 | Auditor disagreement | Rare | wan-huiyan(討論), alecnielsen(circuit breaker) |
| 39 | Audit blind-spot detection | Rare | **dinosn Closure Gate**（捏造PoC/重篤度不当引下げの検出） |
| 40 | Audit-the-audit（findingsの再検証） | Rare（実証あり） | **cloudflare Phase6**, **dinosn Closure Gate** — 両者ともFull評価・実装確認済み |

**真に空いている領域（Novel/Rare、実証実装なし）: #16, #22, #28, #35, #37**
これらは「監査計画自体を検証する」「テストを証跡として統合する」「仮定を明示的に記録する」「次回監査で未探索領域を優先する」という、**Findingsの検証ではなくAudit Plan/Processそのものの検証・改善**に関わる項目である点が共通している。

---

## 3. Closest Competitors TOP10

| # | Repo | 近い理由 | 同じ点 | 違う点 | 単独/組み合わせで代替可能か |
|---|---|---|---|---|---|
| 1 | **cloudflare/security-audit-skill**（★3.3k） | 提案パイプラインの大部分を実装済み | Multi-agent, Adaptive routing, Evidence, Runtime verify, Coverage, History, Audit-the-audit | セキュリティ監査に限定（一般的な正当性・パフォーマンス等は対象外）。Invariant抽出は無い | **セキュリティ領域なら単独でほぼ代替可能** |
| 2 | evilsocket/audit（★852） | cloudflareの明示的な再実装 | 同上（8段階、モデル別ルーティング） | #1のバリエーション。新規性なし | 代替可能（#1と同義） |
| 3 | **dinosn/raptor-loop-hunt**（★217） | Coverage/History/Audit-the-audit実装が最も精緻 | 網羅性台帳、永続KB、Closure Gate | 脆弱性ハント特化。ドメイン汎用性なし | Coverage/History部分は単独で代替可能 |
| 4 | elementalsouls/Claude-BugHunter（★4.4k） | 「自然言語で書くと該当Skillが自動起動」という体験が酷似 | NL起動、フルパイプライン | バグバウンティ/レッドチーム文脈限定 | 部分代替 |
| 5 | trailofbits/skills（★7k） | 監査+検証系Skillの網羅的カタログ（property-based/mutation testing等） | 監査ドメインの幅広さ | 単一パイプラインではなく個別Skillの集合。Adaptive plan生成は無い | 組み合わせれば要素技術は代替可能 |
| 6 | danpeg/bug-hunt / codexstar69/bug-hunter | Hunter/Skeptic/Refereeパターンの原型（酷似した2実装が既に存在） | Adversarial multi-agent | Adaptive/Coverage/Historyなし | 敵対的検証部分は代替可能 |
| 7 | wan-huiyan/agent-review-panel | ドメイン自動判定でペルソナ選定 | Adaptive reviewer selection, 根拠検証 | Invariant/Coverage/Historyなし | 部分代替 |
| 8 | levnikolaevich/claude-code-skills（★559） | 「証跡 or 明示的非該当理由」の思想が仮説Dに近い | Evidence-or-reason方式 | 単一パイプラインでなくSkill集合 | 部分代替 |
| 9 | schatt93/universal-audit-skill（★0） | **コンセプトレベルでは提案と最も一致**（Stage D「Audit of the Audit」含む） | 全ての仮説A-Fを仕様上謳う | **未実装・未実証（★0、単一仕様書）** | 仕様は代替も、実装は存在しない=実質「白紙」 |
| 10 | **Anthropic公式 Managed Code Review + `/code-review`** | 製品レベルで適応的深度・証跡検証・重複排除を標準提供 | Dynamic depth(effort levels), Evidence verification, Dedup, Severity | 汎用的なNL監査観点選択（セキュリティ以外の任意観点への拡張）やInvariant抽出、Audit debt管理は無い | 基本機能は代替される。差別化は"その先"にしかない |

---

## 4. Combination分析（Phase 5）

提案の核心である「全部乗せ」パイプライン：

```
Project Understanding → Invariant Extraction → Risk Model → Adaptive Audit Plan
→ Evidence-driven Audit → Adversarial Verification → Coverage → History → Audit-the-Audit
```

**結論: この全チェーンをエンドツーエンドで実証済み実装している競合は存在しない。**

- `cloudflare/security-audit-skill` + `dinosn/raptor-loop-hunt` の組み合わせで、Invariant Extraction以外の全ステップは実質カバーされる（ただし両者ともセキュリティ/脆弱性監査というドメインに固定）。
- `schatt93/universal-audit-skill` は全チェーンを**仕様として**謳うが、★0・単一Markdown文書であり動作実装が存在しない。
- Invariant Extraction（ビジネスロジック⇔コードの対応付け）を試みているのは `dystopiaxyz/hound-audit-ai` のみで、★0・未使用の研究コード。

したがって「組み合わせで代替可能か」（Phase 9）への回答：

> **セキュリティ監査という文脈に限定すれば、cloudflare/security-audit-skill 1つでこのチェーンの大部分（Invariant以外）を代替できる。** ドメインを一般化（パフォーマンス・アーキテクチャ・データ整合性等）し、かつ監査タイプを横断してCoverage/Audit-Debtを永続管理する部分だけは、既存Skillの組み合わせでは再現できない — 別設計が必要。

---

## 5. Novelty Analysis（本当に残っている差別化要素）

1. **ドメイン非依存の適応的スコープ選択**
   既存の"Adaptive"実装（cloudflare, tripinfinite-gif, wan-huiyan等）は全て「セキュリティ」または「一般的バグ」という単一ドメイン内での適応であり、「このプロジェクトには何の監査（性能／可用性／データ整合性／UX的正しさ等）が必要か」を自然言語から一段上のレベルで判定する実装は確認できなかった。

2. **監査タイプを横断した永続Coverage/Audit-Debt管理**
   `cloudflare`（ラン間で重複排除）や`dinosn`（永続KB）は履歴を持つが、いずれも**単一の監査系統内**（同じセキュリティ監査を繰り返す想定）。「先週のセキュリティ監査では手つかずだった領域を、今回のパフォーマンス監査で優先する」といった**監査タイプ横断の統合管理**は未確認。

3. **Invariant抽出（仮説B/C）**
   最も野心的だが最もリスクが高い。実証実装は`hound-audit-ai`（★0）のみで、これは「未解決の難問」であることを示唆している。ここを差別化の中心に据えるのはハイリスク。

4. **Audit-plan自体への敵対的検証（仮説F, Feature #37）**
   Findingsを検証する仕組み（Audit-the-audit）は`cloudflare`/`dinosn`で実証済みだが、**「そもそもこの監査計画は十分か」を計画段階で攻撃する**実装は未確認（schatt93が仕様レベルで言及するのみ）。ここは実装すれば明確な新規機能になり得る。

**結論**: 個別要素技術（Multi-agent, Adversarial, Evidence, Audit-the-audit）はコピーではなく差別化要素にはならない。差別化できるとすれば「①ドメイン非依存性」「②監査タイプ横断のAudit Debt管理」「④Audit Planへの敵対的検証」の**組み合わせ**であり、③Invariant抽出は理想だが未解決領域として切り離すべき。

---

## 6. 100-Generation Evolution（要約）

| 世代 | 内容 | 競合確認結果 |
|---|---|---|
| Gen 1（「バグチェックして」） | NLトリガー | Saturated（全Skill共通） |
| Gen 10（Multi-agent） | 複数エージェント | Common（danpeg, cloudflare, Dimillian等） |
| Gen 20（Adversarial review） | 敵対的レビュアー | Common（danpeg Skeptic, addyosmani, cloudflare Validate） |
| Gen 30（Adaptive reviewer selection） | 動的レビュアー選定 | Common（wan-huiyan, alanchn31） |
| Gen 40（Risk-based audit plan） | リスクベース計画 | Common（cloudflare, tripinfinite-gif） |
| Gen 50（Evidence-driven findings） | 証跡ベース | Saturated |
| Gen 60（Runtime verification） | 実行時検証 | Rareだが実装あり（cloudflare fuzzing, dinosn PoC） |
| Gen 70（Coverage / unverified areas） | 網羅性測定 | Rareだが実装あり（**dinosn**が最先端） |
| Gen 80（Audit history） | 監査履歴 | Common（cloudflare, sari3l, dinosn） |
| Gen 90（Invariant extraction） | 成立条件抽出 | **Novel**（hound-audit-aiのみ、★0未使用） |
| Gen 100（フルチェーン） | 上記全部の統合 | **未実証。schatt93が仕様のみ提示、実装なし** |

「100世代目だから差別化できる」わけではない、という原文の注意書き通り、Gen100のフルチェーンはGen90（Invariant）の未解決さに引きずられてリスクが高い。**現実的な出発点はGen70-80相当（Coverage+History）にGen40相当（ドメイン非依存のRisk-based plan）を足した水準**であり、Gen90-100は将来拡張として切り離すのが妥当。

---

## 7. 差別化スコア（Phase 7）／実装価値評価（Phase 10）

### 差別化スコア: **5/10**
（「5〜6: 既存Skillにない明確なワークフローがある」に該当。「7〜8: 異なる問題設定」には届かない — 監査という問題設定自体はcloudflare/dinosnと同一であり、差はスコープの汎用性と横断的な状態管理に限られるため）

### 実装価値評価（アシスタントによる工学的判断。Web検証不可のため事実ではなく評価であることを明示）

| 項目 | スコア/10 | 根拠 |
|---|---:|---|
| 技術的実現可能性 | 7 | Subagent/Hooks/構造化JSON等は標準的Claude Code機能。Invariant抽出のみ未解決 |
| Claude Codeとの適合性 | 8 | Task-tool subagentパターンと自然に整合 |
| 実装難易度 | 6（中〜高） | 状態管理・スキーマ設計・複数フェーズ制御が必要 |
| Token/コスト | 4（中〜高） | agent-review-panel実例で$3-20/run。同水準を想定 |
| 実行時間 | 5（中〜長） | 同実例で6-15分。フルチェーンではさらに長時間化の恐れ |
| False Positive削減効果 | 8 | cloudflare/dinosnで実証済みのadversarial verificationパターンを踏襲可能 |
| False Negative削減効果 | 5 | Coverage台帳は有効だが保証はない |
| ユーザー価値 | 6（スコープ次第） | 汎用化とAudit Debt管理に絞れば価値あり。フルチェーンだと過剰投資リスク |
| 保守性 | 5 | 複数フェーズ+永続状態はcloudflareスキル同様の保守負担 |
| 他Agentへの移植性 | 5 | Task-tool依存部分はClaude Code固有。プロンプト部分はcraigkitterman型の多CLI対応で移植可能 |

---

## 8. Risk Register

| リスク | 深刻度 | 対策 |
|---|---|---|
| Agentが存在しないバグを作る（Hallucinated finding） | 高 | cloudflare/dinosn型のIndependent Verificationフェーズを必須化 |
| Evidenceが弱い | 中 | levnikolaevich型「証跡 or 明示的非該当理由」を必須化 |
| Runtime verificationできない環境がある | 中 | fuzzing/harness不可の場合は静的証跡のみで重篤度を自動的に1段階下げる（skillet方式） |
| Audit Plan自体が間違う | 高（未解決領域） | Feature #37（Audit-plan verification）を独立フェーズとして実装。既存実装なしのため要検証しながら育てる |
| Coverageが見せかけになる | 中 | dinosn型のTRIED.md（強制網羅リスト）を採用し、恣意的な「対象外」判定を防ぐ |
| Token消費が大きい | 中〜高 | Anthropic `/code-review`のeffort level設計を参考に、深度を明示的に選択可能にする |
| 大規模Repoで遅い | 中 | 差分監査（Change-aware re-audit）をデフォルトにし、フルスキャンはオプトインにする |
| **既存Skillとの差が実質ない** | **高（最重要リスク）** | セキュリティドメインに閉じた実装は絶対に避ける。差別化の核（ドメイン非依存性+横断的Audit Debt管理）を最初のリリースから明確に打ち出す必要がある |

---

## 9. Naming Analysis（命名分析）

### 9.1 現在の暫定名の状態

| 候補 | GitHub衝突 | 判定 |
|---|---|---|
| `adaptive-audit` | **完全一致は本リポジトリ自身のみ**（`kajisho5/adaptive-audit`）。第三者の同名衝突なし | 衝突リスク低 |
| `adaptive audit`（フレーズ） | 直接の同名OSSなし。ただし"Adaptive"という名のAIエージェント監査ログ企業（adaptive.live）が存在 | 低〜中 |
| `adaptive-audit-engine` / `adaptive audit engine` | GitHub上にリポジトリなし。商用の "Adaptive Compliance Engine (ACE)"（製造業/製薬向けeQMS）が同じ命名パターンだが別ドメイン | **12候補中最もクリーン** |
| `audit-engine` | 440+件がGitHub上に存在（`rcpch/rcpch-audit-engine`等） | 高（汎用語として飽和） |
| `software-audit` | 200+件存在 | 高（汎用語として飽和） |
| `evidence-audit` | 完全一致が2件存在（低star） | 中 |
| `audit-orchestrator` | 完全一致が5件以上存在。うち1件はまさにClaude Code向け監査オーケストレータ（`cegape/audit-orchestrator`） | 中 |
| `audit-planner` | 完全一致が4件存在 | 中 |
| `software-verifier` | 完全一致が3件存在（うち1件は概念的に近い） | 中 |
| `code-verification` | ブランド衝突は無いが、「verification code（認証コード/OTP）」関連リポジトリが1,500+件ヒットし検索汚染リスクが大きい | **却下推奨（SEO衝突）** |
| `adaptive-verifier` | 明確な衝突なし | 低 |

### 9.2 事前ブリーフ記載の3claim検証結果

| Claim | 判定 |
|---|---|
| "ReviewEngine"というAgent Skills互換の複数専門家レビューシステムが存在する | **確認できず（NOT FOUND）**。類似パターンは複数存在するがこの名称のプロジェクトは発見できなかった。元ブリーフの誤記/推測の可能性 |
| 複数の"skill-audit"リポジトリがSkill自体の構造/悪性挙動を監査している | **確認（CONFIRMED）**。`aptratcn/skill-audit`, `dabit3/skill-audit`, `pors/skill-audit`等、複数の独立した実装が存在。GitHub Topic `skill-audit`も存在するほど混雑した領域 |
| Cloudflareのsecurity-audit-skillがRecon→Hunt→Validate→Report(+構造化出力/独立検証)の多段構成である | **確認（CONFIRMED）**。SKILL.mdで6フェーズ構成を直接確認 |

### 9.3 命名判定

- **Repository名**: **KEEP** — `adaptive-audit` は第三者衝突がなく、暫定名として継続使用して問題ない。
- **Skill名**: **MODIFY（保留）** — 現時点でのスコープ（フルチェーン仮説）のままなら"Adaptive Audit Engine"は「adaptive」「audit」「engine」という、差別化要素にならない一般語の組み合わせであり、cloudflare/security-audit-skill等と誤認されるリスクがある。**§5で絞り込んだスコープ（ドメイン非依存性 + 監査タイプ横断のAudit Debt管理）が固まった段階で改めて命名すべき。**
- 参考候補（スコアリングは絞り込み後に実施推奨）: `audit-debt` / `scope-audit` / `audit-coverage-ledger` 等、"何を監査するか"ではなく"何を横断的に管理するか"を軸にした名称の方が、実際の差別化要素を正しく想起させる可能性が高い。

---

## 10. Final Architecture（最終候補・絞り込み版）

Phase 11の判定に基づき、**フルチェーンではなくスコープを絞った以下の構成を推奨**：

```
Natural Language Request
  → Domain-Agnostic Scope Classification（セキュリティに限定しない監査観点判定）
  → Risk-Aware Adaptive Audit Plan（cloudflare/tripinfinite-gif型を参考、ただし多ドメイン対応）
  → Evidence-Driven Audit（既存パターンを流用: Task-tool subagent、証跡 or 明示的非該当理由を必須化）
  → Adversarial Verification（danpeg/cloudflare型のHunter→Skeptic→Independent Verify）
  → Cross-Audit-Type Coverage / Audit-Debt Ledger（★差別化の中核。dinosnのTRIED.md型台帳を監査タイプ横断に拡張）
  → Audit-Plan Self-Verification（★差別化の中核。計画自体を独立フェーズで攻撃・未実証領域のため段階的に検証しながら実装）
```

**Invariant Extraction（仮説B/C）は将来拡張の実験的モードとして切り離す**（未解決領域、hound-audit-ai以外に前例なし）。

---

## 11. Go / No-Go 判定

### 判定: **CONDITIONAL GO**

満たしている点:
- 実装可能性は高い（Claude Codeの標準機能で構築可能）
- 既存Skillの単純コピーではない組み合わせが存在する

満たしていない点（要改善）:
- 現状のフルチェーン構想は、cloudflare/security-audit-skill + dinosn/raptor-loop-huntの組み合わせで大部分（ドメインをセキュリティに限定すれば）代替可能であり、差別化が狭い
- Invariant抽出という最も野心的な要素は未解決領域であり、コア機能として約束すべきではない

### 削るべき機能 / コアにすべき機能

| 分類 | 機能 |
|---|---|
| **コアにする（差別化の源泉）** | ドメイン非依存の適応的Audit Plan生成、監査タイプ横断のCoverage/Audit-Debt管理、Audit-Plan自体への敵対的検証 |
| **既存パターンを流用する（再発明しない）** | Multi-agent adversarial review（Hunter/Skeptic/Referee型）、Evidence-then-Verifyパイプライン、Independent Verification（cloudflare/dinosn型） |
| **将来拡張として切り離す** | Invariant Extraction（仮説B/C）— 未解決領域。実験的opt-inモードとして提供し、コアの約束には含めない |

### 空欄の記入（判定基準）

> このSkillは、**「セキュリティ/バグ検出という単一ドメインに閉じず、かつ監査タイプ（セキュリティ・性能・アーキテクチャ・データ整合性等）を横断して"何を検証済みで何が未検証か"を永続管理する」**という問題を、既存Skillとは異なる**「ドメイン非依存の適応的Audit Plan生成 + 監査タイプ横断のAudit-Debt台帳 + 監査計画自体への敵対的検証」**という方法で解決する。

> ただし、上記の個別要素技術（Multi-agent, Evidence, Runtime Verify, Audit-the-Audit）はcloudflare/security-audit-skill（★3.3k）やdinosn/raptor-loop-hunt（★217）に実装済みであり、これらを組み合わせれば「セキュリティ監査」という範囲内では代替可能である。差別化が成立するのは、範囲をセキュリティに限定しない場合のみである。

---

## 付録 A. 検索で確認できなかった/未確認事項

- 各リポジトリのStar数・最終更新日はGitHub APIではなくWeb取得時点のスナップショットであり、正確な数値ではなく概算として扱うこと。
- `GK-Edge/AI-Audit`, `Nayjest/Gito`, `bobmatnyc/ai-code-review`, `Nikita-Filonov/ai-review` はスニペットのみで実装未検証。
- skilletの37個中2Skillのみ詳細確認。universal-audit-skillの`adapters/`等サブディレクトリは個別に開いていない（仕様書内の自己申告に基づく評価）。

---

*本レポートは実装仕様書ではなく、実装可否を判断するための調査結果である。「世界初」「唯一」「革新的」等の表現は意図的に使用していない。*
