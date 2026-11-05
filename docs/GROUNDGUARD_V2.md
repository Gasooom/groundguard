# GroundGuard V2 — Master Specification

**Status:** DRAFT, proposed for review. Nothing in this document is implemented yet.
**Owner:** Abualgasim Ibrahim (`Gasooom`)
**Applies to:** GroundGuard v0.1.0 → v2.0.0
**Companion documents:**
[ARCHITECTURE_V2.md](ARCHITECTURE_V2.md) ·
[EVALUATION_METHODOLOGY.md](EVALUATION_METHODOLOGY.md) ·
[IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md) ·
[TECHNICAL_DECISIONS.md](TECHNICAL_DECISIONS.md)

> Reading rule for this document: **"is"** describes what exists in v0.1.0 and was
> verified against code. **"will"** describes a proposal. Every number quoted for
> v0.1.0 was reproduced by running the repository's own code against the
> repository's own benchmark files. Section 5 gives the exact procedure.

---

## 1. Product vision

GroundGuard is a **reliability gate** that sits next to an LLM, RAG, or agent
application. It turns every generated answer or agent trace into an **auditable
decision** (`ACCEPT`, `FLAG`, `REJECT`, or `HUMAN_REVIEW`), and every part of that
decision can be traced:

```
answer / trace
  → atomic claims
    → evidence spans (source id + character offsets)
      → per-claim verdict  (SUPPORTED | CONTRADICTED | NOT_ENOUGH_INFO) + verifier + confidence
        → checks (relevance, safety, citations, RAG retrieval, agent tool use)
          → versioned policy rules
            → decision + rule trace + evaluator manifest
```

The product promise is narrow on purpose:

> *"Given the evidence you supplied, here is which claims are supported, which
> are contradicted, which cannot be verified, and the policy-driven decision.
> We publish this decision's measured false-accept rate on a frozen held-out
> dataset, with confidence intervals."*

GroundGuard does **not** promise universal factual truth. It does **not** treat
an LLM judge as ground truth. It does **not** claim a production guarantee it
has not measured.

## 2. Problem statement

Teams shipping LLM features can usually answer "does the demo look right?" They
usually cannot answer the questions that matter once a feature is in production:

| Question a team has | Why it is hard today |
|---|---|
| Which **specific claim** in this answer is unsupported? | Most metrics return one answer-level score |
| Is a claim **unsupported** or **contradicted**? | Many tools collapse both into "unfaithful", but the remediation differs |
| Why was this answer rejected, and by which rule? | Scores are produced, but decisions are improvised downstream |
| Did the new model, prompt, or retriever **regress**? | Evaluations are run ad hoc, without frozen datasets or CI gates |
| How often do we **accept a bad answer**? | False-accept rate at the operating threshold is rarely measured |
| Did retrieved content **inject instructions**? | Safety checks look at the user prompt or the answer, not the retrieved context |
| Did the agent call the right tool with valid arguments, and was the final answer grounded in tool output? | Final-answer evaluation ignores the trajectory |

## 3. Target users

1. **Applied AI engineers** building RAG or agent features, who need a
   per-request gate and explanations they can debug.
2. **ML / evaluation engineers**, who need reproducible benchmark runs,
   regression detection, and model or prompt comparisons.
3. **Engineering managers and reviewers**, who need an auditable record of why
   outputs were accepted, plus measured error rates.
4. **Platform / security engineers**, who need PII and injection signals and a
   service with authentication, limits, and audit logs.

Explicitly **not** targeted in v2: end-users, non-technical analysts, and
large-scale observability (traces at millions per day).

## 4. Core use cases

| # | Use case | Interface | Milestone |
|---|---|---|---|
| U1 | Gate a single RAG answer at request time | `POST /v2/evaluate`, SDK `client.evaluate()` | M2–M3 |
| U2 | Inspect *why* an answer failed, claim by claim | Dashboard claim inspector, `GET /v2/evaluations/{id}` | M2, M8 |
| U3 | Batch-evaluate a dataset offline | `groundguard eval --input file.jsonl`, `POST /v2/evaluate/batch` | M7 |
| U4 | Block a merge when reliability regresses | `groundguard bench compare --fail-on-regression` in CI | M1, M7 |
| U5 | Compare two models/prompts on the same frozen dataset | `groundguard bench compare runA runB` | M1, M7 |
| U6 | Check RAG retrieval quality and citation correctness | `/v2/evaluate` with chunked context + citations | M5 |
| U7 | Evaluate an agent execution trace | `POST /v2/traces/evaluate` | M6 |
| U8 | Configure acceptance policy per application | `policy.toml`, versioned | M3 |

## 5. Existing system assessment (v0.1.0 audit)

### 5.1 What exists and works

- A layered package (`domain/`, `application/`, `evaluation/`, `storage/`,
  `api/`). The core depends only on the standard library.
- Grounding (`domain/grounding.py` + `domain/claims.py`): sentence-level token
  overlap against context sentences, with a numeric-value agreement check and
  question-type checks.
- Relevance (`domain/relevance.py`): overlap between question keywords and the
  answer, with light stemming, five hand-written alias groups, and question-type
  checks.
- Contradiction (`domain/contradiction.py`, `propositions.py`,
  `proposition_comparison.py`, about 2,300 lines): regex extraction of 18 fixed
  predicates (`founded`, `sells`, `operates_in`, `capital_city`,
  `has_employees`, …) into `(subject, predicate, object, attributes)`, compared
  structurally, plus question-aware handling of additive predicates.
- Safety: 4 PII regexes (email, phone, IPv4, card-like numbers) and about 14
  prompt-injection regexes in 4 categories, all applied **to the answer only**.
- Decision (`domain/decision.py`): hard rules (unsafe / contradictory /
  unsupported / irrelevant → `REJECT`; partial → `FLAG`), then
  `min(grounding, relevance, 1 − contradiction) ≥ 0.70` → `ACCEPT`, else `FLAG`.
  Every decision carries a textual reason.
- Persistence: SQLite, one JSON blob per evaluation. API: FastAPI with 6
  endpoints. Dashboard: inline HTML that renders values with `textContent`.
  Docker image with a named volume.
- 224 test functions across 45 files.

### 5.2 Independent verification of published results

| README claim | Reproduced | Notes |
|---|---|---|
| Grounding 64.40% (161/250) | **64.40%** | Matches |
| Relevance 97.20% (243/250) | **97.20%** | Matches |
| Contradiction 99.20% (248/250) | **248/250 only when the annotator's gold `evidence` field is the input** | Through the production path (`context`, as `/evaluate` does), the result is **245/250 = 98.0%**. Without the question argument it is 92.0% |
| "250 human-labeled records" | **99 unique (question, context, answer) triples** | 70 singletons + 29 templates repeated 6–7× (e.g. `synthetic_071/100/129/158/187/216/245` are identical). 68 unique contexts. Median context length is 6 words. 1 answer has more than one sentence |
| Source mix 125 synthetic / 125 public (manifest) | 210 synthetic, 20 public_text, 20 manual_annotation | Construction targets not met |
| Deduplicated (99 unique) | Grounding **59.6%**, relevance 98.0%, contradiction **94.9%** (contradiction recall 20/25 = 80%, 0 false positives) | Duplicates inflate every metric |
| Public-text subset (20) | Grounding **50%**, contradiction **85%** | The best available proxy for generalization |
| PII 20/20, injection 16/16 | Reproduced | Small sets written alongside the regexes they test |
| End-to-end decision on the 250 records (gold "reliable" = SUPPORTED ∧ RELEVANT ∧ NOT_CONTRADICTORY) | FAR **8/168 = 4.8%**, FRR **50/82 = 61.0%** | The README threshold table measures `reliability_score` alone, not the decision engine |

**Generalization probes** (hand-written, outside the benchmark):

| Context | Answer | v0.1.0 decision | Correct outcome |
|---|---|---|---|
| "Acme Corp is headquartered in Berlin…" | "Acme is not headquartered in Berlin." | **ACCEPT** | REJECT (contradiction) |
| "Drug X is approved to treat hypertension in adults." | "…in children." | **ACCEPT** | REJECT (contradiction) |
| "Customers may request a refund within 30 days of purchase." | "Refunds can be requested up to thirty days after buying." | **REJECT** | ACCEPT (paraphrase) |
| "…Refunds are not available for digital goods." | "You can get a refund for digital goods within 30 days." | FLAG | REJECT (contradiction) |

**Methodology defects found:**

1. No dev/test split. Commit `491b85c` added about 1,640 lines that target
   specific benchmark failures (e.g. canonicalizing "ocean basin"), so the
   reported contradiction accuracy is a **training-set** number.
2. The contradiction benchmark test and the decision-metrics test feed
   `record["evidence"]` (oracle evidence) instead of `record["context"]`.
3. Vacuous assertions: `tests/test_relevance_benchmark.py` and
   `tests/test_contradiction_benchmark.py` assert `correct >= 0`, and the
   grounding benchmark test asserts no accuracy bound. These tests cannot fail
   on regression. The README threshold table is also stale: it predates
   commit `491b85c` (current code: FAR 6.55% / FRR 60.98% at 0.70, not
   7.74% / 62.20%). *Fixed in M1.*
4. Label noise. 4 of the 16 unique `PARTIALLY_SUPPORTED` records conflict with
   the guideline's own definition or the annotator's note: `synthetic_075` and
   `synthetic_077` are fully supported but incomplete answers (completeness, not
   grounding); `public_056` is noted "both claims are supported"; and
   `public_065` is noted "otherwise this should be SUPPORTED".
5. A single annotator, with no agreement measurement.
6. Dead code with a latent bug: `contradiction.py::_propositions_conflict`
   references an undefined `evidence` and returns a `ContradictionResult` from a
   function annotated `-> bool`.

### 5.3 What is genuinely strong (preserve)

- **"Unsupported ≠ contradicted"** is a first-class principle, encoded in labels
  and tests. Many tools collapse the two into one score.
- **Conservative aggregation:** severe component failures cannot be averaged
  away.
- **Every decision has a reason.**
- **Clean layering** and a dependency-free core. Frozen dataclasses.
- **A culture of documented limitations**, a sourcing policy with source
  metadata, and per-component regression tests.

### 5.4 What is weak (redesign)

| Area | Weakness | Consequence |
|---|---|---|
| Grounding | Bag-of-tokens overlap. Blind to negation, qualifiers, and paraphrase | False accepts in exactly the cases that matter |
| Contradiction | Closed vocabulary of 18 regex predicates fitted to benchmark templates | Does not transfer to real RAG text |
| Claims | One sentence = one claim. No offsets | Explanations cannot point at evidence spans |
| Benchmark | Duplication, oracle evidence, no held-out set, tiny contexts, one annotator, label noise | Published numbers are not defensible |
| Safety | Answer-only regexes. No indirect injection in retrieved context. No Luhn check, IBAN, or national IDs | The main RAG threat model is unaddressed |
| API | No auth, no rate limit, no input-size limit. `/stats` loads every row into memory. Unvalidated filter values. No API version. No evaluator or config version stored per record | Not adoptable by a team. Old decisions are not reproducible |

**Heuristic components:** all of them. **Components that need external models:**
none today. V2 introduces *optional* model-backed verifiers (see §8, ADR-003).

### 5.5 What a senior reviewer would say, and the response

> "This is regex tuned on 29 templates, and 99.2% is an oracle-evidence number
> on duplicated data."

That criticism is fair. V2's first milestone therefore fixes **measurement
credibility** before adding features (M1).

## 6. Proposed architecture (summary)

V2 is a **modular monolith**: one Python package, one optional HTTP service, and
SQLite by default. A single-node evaluator does not need distributed components.
See [ARCHITECTURE_V2.md](ARCHITECTURE_V2.md) for diagrams.

```
groundguard/
  core/       typed domain model (Claim, EvidenceSpan, ClaimVerdict, CheckResult, Decision, Trace…)
  claims/     claim segmentation (sentence → clause → conjunction split); optional LLM decomposer
  evidence/   context chunking with source ids; pure-Python BM25 candidate selection
  verifiers/  Verifier protocol; lexical (v1 baseline), guards (negation/number/date/qualifier),
              structured_facts (v1 propositions, narrow domain), nli [extra], llm_judge [extra]
  checks/     relevance, pii, injection (answer AND retrieved context), citations, rag_metrics
  agents/     trace schema + deterministic trajectory checks
  policy/     TOML policies → rules → decision + rule trace
  bench/      dataset registry, splits, runner, metrics, run manifests, compare
  domain/     v0.1.0 modules, kept in place and unchanged; reachable via engine="v1"
  api/        /evaluate (v1, unchanged) + /v2/* ; auth, limits
  storage/    SQLite with migrations and indexed columns
  sdk/        thin Python client
  cli.py      groundguard eval | bench run | bench compare
```

## 7. Domain model

All types are frozen dataclasses with explicit `Literal` enums and are
JSON-serializable through one `to_dict()` convention. Shapes:

```python
VerdictLabel = Literal["SUPPORTED", "CONTRADICTED", "NOT_ENOUGH_INFO"]
Decision     = Literal["ACCEPT", "FLAG", "REJECT", "HUMAN_REVIEW"]

@dataclass(frozen=True)
class SourceDocument:     # one retrieved chunk / tool output / reference
    id: str               # caller-supplied (e.g. "doc-3#chunk-2") or generated
    text: str
    kind: Literal["context", "tool_output", "reference"] = "context"
    metadata: Mapping[str, str] = {}

@dataclass(frozen=True)
class Claim:
    id: str               # "c1", "c2", … stable within one evaluation
    text: str             # possibly decomposed text
    answer_span: Span     # (start, end) offsets into the original answer
    origin: Literal["sentence", "clause", "conjunct", "llm_decomposed"]

@dataclass(frozen=True)
class EvidenceSpan:
    source_id: str
    start: int
    end: int
    text: str
    retrieval_score: float

@dataclass(frozen=True)
class ClaimVerdict:
    claim_id: str
    label: VerdictLabel
    confidence: float | None        # calibrated probability if a calibrator exists, else None
    raw_score: float                # verifier-native score, never presented as a probability
    evidence: tuple[EvidenceSpan, ...]
    verifier: str                   # "lexical@1", "guards@1", "nli:<model>@<rev>", …
    rationale: str                  # machine-generated, deterministic for deterministic verifiers
    signals: Mapping[str, object]   # e.g. {"negation_mismatch": True, "number_mismatch": ["30","14"]}

@dataclass(frozen=True)
class CheckResult:                  # relevance, pii, injection, citation, retrieval, agent checks
    name: str
    status: Literal["PASS", "WARN", "FAIL", "NOT_APPLICABLE"]
    score: float | None
    findings: tuple[Finding, ...]   # each with location + evidence + message

@dataclass(frozen=True)
class DecisionResult:
    decision: Decision
    policy_id: str; policy_version: str
    fired_rules: tuple[RuleFiring, ...]    # ordered; first terminal rule wins
    reason: str

@dataclass(frozen=True)
class EvaluatorManifest:            # stored with every evaluation
    groundguard_version: str
    engine: Literal["v1", "v2"]
    verifier_chain: tuple[str, ...]
    config_hash: str                # sha256 of canonical JSON config + policy
    created_at: str                 # ISO-8601 UTC, microsecond precision
```

Agent traces add `Trace(id, goal, steps, final_answer, available_tools)`,
`Step(kind: "llm" | "tool_call" | "tool_result" | "retrieval", …)` and
`ToolCall(name, arguments, result, error)` (§11).

Answer-level labels are **derived** from claim verdicts and are kept for v1
compatibility:

| Claim verdicts | v1 grounding label | v1 contradiction label |
|---|---|---|
| all SUPPORTED | SUPPORTED | NOT_CONTRADICTORY |
| ≥1 SUPPORTED and ≥1 NOT_ENOUGH_INFO, none CONTRADICTED | PARTIALLY_SUPPORTED | NOT_CONTRADICTORY |
| none SUPPORTED, none CONTRADICTED | UNSUPPORTED | NOT_CONTRADICTORY |
| ≥1 CONTRADICTED | per remaining claims | CONTRADICTORY |

## 8. Evaluation methodology (summary)

Full detail is in [EVALUATION_METHODOLOGY.md](EVALUATION_METHODOLOGY.md). Key commitments:

1. **Two-level labels.** Claims carry SUPPORTED / CONTRADICTED /
   NOT_ENOUGH_INFO. Answers carry the derived labels plus a separate
   *completeness* dimension. Completeness is no longer conflated with grounding
   (this resolves label-noise cases like `synthetic_077`).
2. **Frozen, hashed, group-split datasets.** Splits are made by *context group*,
   so near-duplicate contexts cannot leak across dev/test. The test split is
   never inspected while rules are developed.
3. **Production-path inputs only.** Headline numbers use `context`, never gold
   evidence. Oracle-evidence runs are reported separately and labeled
   *oracle*.
4. **Decision-level metrics first.** The primary metric is **FAR** (bad answers
   accepted / all bad answers) at the configured policy, with a 95% bootstrap
   CI. FRR, per-class P/R/F1, confusion matrices, and ECE are secondary.
5. **Verifier independence.** Each verifier is benchmarked alone and in its
   chain, so failures can be attributed to a component.
6. **LLM judges are measured like any other verifier.** Their model id, prompt
   version, temperature, and sampling settings go into the manifest. They are
   never used to *label* test data.

## 9. Claim-level evaluation design

**Pipeline per answer:**

1. **Segmentation** (`claims/segmenter.py`, deterministic). Sentences are split
   with abbreviation and number protection, then clauses on `;` and on
   coordinating conjunctions that separate independent predicates, then
   coordinated object lists ("sells A, B, and C" → three conjunct claims that
   share subject and predicate). Every claim keeps its character offsets into
   the original answer. Non-assertive sentences (questions, hedges such as "I'm
   not sure", meta-text such as "Based on the context") are tagged
   `non_assertive` and excluded from grounding, but are still visible.
2. **Evidence candidate selection** (`evidence/`). Context is split into
   sentence windows that carry `source_id` and offsets. BM25 (pure Python) plus
   numeric/entity overlap boosts. Top-k candidates (default k = 3) go to
   verifiers.
3. **Verification chain.** Verifiers run in order. Guards can *veto* and lexical
   or NLI verifiers *decide*:
   - `guards`: negation polarity mismatch, number/unit mismatch, date mismatch,
     qualifier/scope mismatch (e.g. *adults* vs *children*, *all* vs *some*,
     *before* vs *after*). Mismatched polarity, numbers, dates, or exclusive
     qualifiers on an otherwise high-overlap candidate → `CONTRADICTED`, with
     the mismatch as evidence. A missing qualifier → `NOT_ENOUGH_INFO`.
   - `structured_facts`: the v1 proposition engine, wrapped as a verifier and
     **explicitly scoped** to the predicates it supports. It abstains outside
     that scope.
   - `lexical`: the v1 overlap scorer, retained as the default backend and as a
     baseline.
   - `nli` (optional extra): a local entailment cross-encoder. Entail /
     contradict / neutral probabilities map to the three verdicts.
   - `llm_judge` (optional extra): a versioned prompt with a JSON schema output
     and fixed temperature. It returns a verdict, evidence quote, and rationale.
     The quote must be an exact substring of a candidate, otherwise the verdict
     is downgraded to `NOT_ENOUGH_INFO` (hallucinated-evidence guard).
4. **Calibration.** If a calibrator was fitted on the dev split for this exact
   verifier version, `confidence` is a calibrated probability. Otherwise
   `confidence = None` and the UI says *uncalibrated*.

**Why decomposition is not assumed to improve accuracy:** MiniCheck (Tang et
al., EMNLP 2024) reports that explicit claim decomposition did not consistently
improve fact-checking performance. GroundGuard decomposes for **explainability
and localization**. Its accuracy effect is measured as an ablation (sentence vs
clause vs conjunct) and is not assumed.

## 10. RAG evaluation design

| Dimension | Definition in GroundGuard | Requires | Method |
|---|---|---|---|
| Faithfulness | fraction of assertive claims with verdict SUPPORTED. Contradiction rate is reported separately | question, answer, contexts | claim pipeline (§9) |
| Unsupported-claim rate | NEI claims / assertive claims | same | claim pipeline |
| Contradiction rate | CONTRADICTED claims / assertive claims | same | claim pipeline |
| Citation correctness | for each `[n]`-style citation, does source *n* support the cited claim? Precision = correct citations / citations. Recall = cited supported claims / supported claims | answer citations mapped to source ids | verifier restricted to the cited source |
| Context utilization | fraction of retrieved chunks that support ≥1 claim | contexts | from verdict evidence |
| Context precision (reference-based) | rank-aware precision of chunks relevant to the reference answer | reference answer or relevant-chunk labels | verifier run of reference claims vs each chunk |
| Context recall (reference-based) | fraction of reference claims supported by the retrieved context | reference answer | claim pipeline run on reference |
| Answer relevance | question-answer alignment, plus "answers the asked type" | question, answer | v1 relevance (baseline), optional NLI/embedding backend |
| Indirect injection | instruction-like content inside retrieved context | contexts | injection check on every source document |

**Where GroundGuard adds value beyond RAGAS-style metrics:** RAGAS documents
faithfulness, context precision, and context recall, with context recall
requiring a reference answer. GroundGuard keeps compatible definitions where
they exist, but (a) separates contradiction from unsupported, (b) returns
evidence spans and per-claim verdicts rather than only a score, (c) turns
metrics into a policy decision with a measured FAR, and (d) runs deterministic
verifiers by default, so results are reproducible bit-for-bit. Reference-based
metrics are only computed when a reference is supplied, and the API says
`NOT_APPLICABLE` otherwise.

## 11. Agent evaluation design

**Input:** an execution trace (OpenTelemetry-GenAI-like but self-contained JSON)
with goal, available tool schemas, ordered steps, and a final answer.

| Check | Type | Definition |
|---|---|---|
| Tool allowlist / policy compliance | deterministic | every call's tool name ∈ allowed set; forbidden tools per policy |
| Argument validity | deterministic | arguments validate against the tool's JSON-Schema subset (type, required, enum, min/max, pattern) |
| Unnecessary / redundant calls | deterministic | identical (name, canonical args) repeated without an intervening state change, and call budget exceeded |
| Error handling / recovery | deterministic | a tool error followed by (a) a retry with changed arguments, (b) an alternative tool, or (c) an honest failure report. Silent continuation as if successful → FAIL |
| State consistency | deterministic | claims in later LLM steps or the final answer that contradict earlier tool results (claim pipeline, tool outputs as sources) |
| Final-answer grounding | deterministic + verifiers | final answer claims verified against tool outputs and retrieved docs as `SourceDocument(kind="tool_output")` |
| Tool selection accuracy | reference-based | compare against an expected tool sequence when provided (exact / subsequence / set match, reported separately) |
| Goal completion | reference-based or judge | only with a reference outcome or a declared LLM judge. Never inferred silently |
| Planning quality | out of scope for v2 | no defensible deterministic definition. Documented as a non-goal |

Trace-level decisions use the same policy engine with trace-scoped rules (e.g.
`any_check_failed("argument_validity") → REJECT`).

## 12. Benchmark architecture

```
benchmark/                 (existing directory; one place for data and results)
  datasets/<dataset_id>/<version>/
      records.jsonl          one record per line, schema-validated
      DATASHEET.md           provenance, construction, annotation guide version, known issues
      splits.json            {"dev": [...ids], "test": [...ids]} — group split by context_group
      SHA256SUMS
  results/<run_id>.json      run manifest + metrics + per-record predictions
  baselines/<name>.json      pointer to a run used as regression baseline
```

Datasets planned:

| Dataset | Content | Role |
|---|---|---|
| `gg-legacy-v1@1.0.0` | the 250 v0.1.0 records, unmodified, plus a dedup view (99) | regression only. **Seen data: never a generalization claim** |
| `gg-legacy-v1@1.1.0` | label corrections with an audit log (old → new label, reason) | regression on corrected labels |
| `gg-claims-v2` | multi-sentence contexts (50–400 words), multi-claim answers, claim-level labels, NEI, negation/qualifier/paraphrase/number/date phenomena, multiple domains | primary dev/test |
| `gg-rag-v2` | multi-chunk contexts with citations and reference answers | RAG metrics |
| `gg-agent-v1` | 30–50 traces with injected faults (bad args, wrong tool, ignored error, ungrounded final answer) | agent checks |
| `gg-safety-v2` | expanded PII (with Luhn-valid/invalid cards, IBAN) and injection, both direct and embedded in context | safety |
| external (optional) | subsets of LLM-AggreFact, RAGTruth via download scripts, subject to license and network access | out-of-distribution check. Never vendored |

Runs are reproducible: a run manifest records the git SHA, dirty flag, dataset
id + version + sha256, split, engine, verifier chain, config hash, policy
version, Python version, and wall-clock timings.

## 13. API and SDK strategy

- `POST /evaluate` and existing `GET` routes stay **byte-compatible** (frozen by
  snapshot tests).
- New under `/v2`:
  - `POST /v2/evaluate`: `{question, contexts:[{id,text}] | context, answer, citations?, reference?, policy?, options?}` → claims, verdicts, checks, decision, manifest
  - `POST /v2/evaluate/batch`: up to N items (configurable), synchronous. Async jobs are deferred until needed
  - `POST /v2/traces/evaluate`
  - `GET /v2/evaluations`, `GET /v2/evaluations/{id}`, `GET /v2/stats` (SQL aggregation, time-bucketed)
  - `GET /v2/policies`, `GET /v2/benchmarks/runs`, `GET /v2/benchmarks/runs/{id}`
- Errors use one shape: `{"error": {"code", "message", "details"}}`. Input-size
  limits return 413 and rate limits return 429.
- **SDK** (`groundguard.sdk.Client`): stdlib `urllib` by default, typed
  responses that mirror `core` types, retries on 429/5xx with backoff. **The
  library can also be used in-process** (`groundguard.evaluate(...)`) without
  the server. This is the most common integration path.
- **CLI:** `groundguard eval`, `groundguard bench run`, and
  `groundguard bench compare --baseline X --fail-on-regression "far>+0.01"`.
  The exit code drives CI.
- Webhooks are **deferred**: no demonstrated need yet (ADR-010).

## 14. Dashboard requirements

Server-served static HTML + vanilla JS, no CDN, no build step. Every number
shown must come from stored evaluations or stored benchmark runs. Pages:

1. **Overview:** decision distribution over time, FAR/FRR of the *currently
   configured policy* from the latest benchmark run (with CI and dataset id),
   safety findings count.
2. **Evaluations:** filterable history (decision, policy version, date, check failures).
3. **Evaluation detail / claim inspector:** answer with claims highlighted by
   verdict, click a claim to see evidence spans highlighted in the source,
   verifier, confidence or "uncalibrated", fired rules in order.
4. **Benchmarks:** runs list, per-class metrics, confusion matrices, threshold
   curves (FAR vs FRR), calibration (reliability diagram).
5. **Compare / regression:** two runs side by side, metric deltas with CIs,
   per-record flips (records whose decision changed).
6. **Configuration:** active policy (read-only render of TOML) and verifier chain.
7. **API docs:** link to FastAPI OpenAPI plus curated examples.

Visual direction: dense, typographic, technical. No decorative metrics, no
animation beyond state transitions. Accessible color pairs for verdicts, which
also carry icons and text, so color is never the only signal.

## 15. Security and privacy

| Control | Design | Limitation stated |
|---|---|---|
| Authentication | API keys (`gg_<prefix>_<secret>`), stored as SHA-256 hashes with prefix lookup, constant-time compare. Disabled only with an explicit `GROUNDGUARD_AUTH=disabled` for local dev | No SSO/OAuth in v2 |
| Rate limiting | in-process token bucket per key | per-process only. Multi-replica deployments need an external limiter |
| Input validation | size caps (answer, context, number of sources, batch size), enum validation for filters, strict pydantic models | |
| Data isolation | every row tagged with `tenant_id` derived from the key. All queries are scoped | logical isolation in one SQLite file, not physical |
| Sensitive data | `store_payloads = full | redacted | none` per policy. Redaction replaces detected PII spans before persistence | Redaction is only as good as PII detection, which is regex-based |
| Auditability | append-only evaluations table. Manifest + policy version + rule trace per row | |
| PII detection | regex + validators (Luhn, IBAN mod-97). Optional Presidio integration as an extra | No guarantee for names or addresses with regex |
| Prompt injection | pattern detector applied to answer **and** every source document, with source-level findings | Pattern-based detection is bypassable. Documented as a signal, not a defense |

GroundGuard makes **no security guarantee**. It provides signals plus a
configurable policy over them.

## 16. Testing strategy

| Layer | What | Rule |
|---|---|---|
| Unit | each segmenter rule, guard, verifier, metric, policy rule | table-driven, one behavior per test |
| Property | segmentation offsets always map back to answer text. Metrics stay within [0,1]. Policy evaluation is deterministic | stdlib-only: hand-rolled randomized tests with fixed seeds (no Hypothesis dependency) |
| Equivalence | `engine="v1"` and the v1 default policy reproduce v0.1.0 outputs on all 250 records | must stay green forever |
| Probe suites | negation, qualifier, paraphrase, number/date, indirect injection | each probe documents expected verdict + rationale |
| Benchmark regression | metrics on `gg-legacy-v1` and dev splits must not drop below committed baselines by more than a declared tolerance | replaces vacuous `>= 0` asserts. **Test split is not used in CI tuning** |
| API contract | v1 snapshot tests, v2 schema tests, auth/limit tests | |
| Reproducibility | the same run twice produces an identical predictions hash (deterministic engines) | |

Never weaken an existing test. If a v1 test conflicts with corrected semantics,
it moves under `engine="v1"` with a comment linking the ADR. It is not deleted.

## 17. Deployment strategy

- **Library first:** `pip install groundguard`. Extras: `[api]`, `[nli]`, `[llm]`, `[dev]`.
- **Service:** the existing Dockerfile pattern, non-root user, healthcheck,
  `GROUNDGUARD_*` env config, SQLite volume. Optional Postgres is **deferred**
  until a multi-replica requirement exists.
- **CI:** GitHub Actions running lint, type-check (mypy strict on new
  packages), tests, a benchmark regression gate on dev/legacy, and a Docker
  build.
- Startup does not open the database at import time (today `_store` is created
  on import). It uses an app factory with lifespan.

## 18. Implementation milestones

See [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md). Summary:

| M | Theme | Exit criterion |
|---|---|---|
| M0 | Specification (this document set) | owner approval |
| M1 | Benchmark integrity and harness | honest v0.1.0 baseline committed and reproducible. Vacuous tests replaced |
| M2 | Claim-level pipeline + guards | probe suite passes. v1 equivalence green. `/v2/evaluate` |
| M3 | Policy engine | v1 policy reproduces v1 decisions exactly. HUMAN_REVIEW band |
| M4 | Held-out dataset, calibration, optional NLI | test-split report with CIs and error analysis |
| M5 | RAG evaluation | citations, retrieval metrics, indirect injection |
| M6 | Agent trace evaluation | `gg-agent-v1` report |
| M7 | Developer infrastructure + security | auth, limits, batch, SDK, CI gate |
| M8 | Dashboard | claim inspector, benchmark and regression pages on real data |
| M9 | Validation and release | latency/throughput report, README rewritten from run artifacts |

## 19. Risks and trade-offs

| Risk | Impact | Mitigation |
|---|---|---|
| Honest numbers are lower than published v0.1.0 numbers | perceived regression | Publish both, with the methodology change explained. Credibility is the point |
| Single annotator | label bias, no agreement metric | Second annotator for ≥ 20–30% of `gg-claims-v2` test (owner to arrange). Otherwise state as a limitation |
| Deterministic verifiers plateau | grounding stays weak on paraphrase | Optional NLI backend. Measured, not assumed |
| Model extras add weight (~hundreds of MB) and latency | adoption friction | Extras stay optional. Latency is reported per backend |
| Network restrictions block external datasets/models in CI | missing OOD numbers | Download scripts runnable locally. CI runs only vendored datasets |
| Overfitting rules to dev | inflated dev numbers | Frozen test split. Test is evaluated only at milestone close, and every look is logged in the run registry |
| Scope creep (agents, dashboard) | unfinished core | Strict milestone order. M1–M4 are the core deliverable |
| LLM-judge nondeterminism | irreproducible runs | Manifest records model + prompt version. Repeated-run variance is reported. Excluded from default chain |

## 20. Measurable success criteria

These are targets, not claims. Each one is verified by an artifact in `benchmark/results/`.

1. **Reproducibility:** `groundguard bench run --dataset gg-legacy-v1` produces
   an identical predictions hash on two machines (deterministic chain).
2. **Traceability:** every number in README links to a run file with dataset hash and git SHA.
3. **Probe safety:** 0 false accepts on the documented negation/qualifier probe suite.
4. **Held-out decision quality:** on `gg-claims-v2` test, FAR and FRR are
   published at the default policy with 95% bootstrap CIs. Initial target:
   FAR ≤ 5% for answers containing a contradicted or unsupported claim. FRR is
   published whatever it is.
5. **Claim-level quality:** per-verdict precision/recall on test, with
   `CONTRADICTED` recall reported separately (the expensive error).
6. **Calibration:** ECE on test reported for every verifier that emits `confidence`.
7. **Compatibility:** v1 equivalence suite green. No existing test weakened.
8. **Latency:** p50/p95 per verifier chain on a fixed hardware profile, published with the profile.

---

## Appendix A — Critical review of this specification

The draft was challenged from three perspectives. This section records what
changed as a result.

### A.1 Principal AI Engineer

| Challenge | Finding | Revision |
|---|---|---|
| Are we measuring reliability or generating scores? | The draft led with per-component accuracy | **Primary metric is now decision-level FAR at the configured policy**. Component metrics are diagnostic |
| Are components independent and testable? | Guards and verifiers were entangled in the draft chain | Each verifier is benchmarked in isolation **and** in the chain. Guards can only veto with an explicit signal |
| Can we explain failures? | Draft verdicts had a score but no location | `EvidenceSpan` with offsets plus `signals` is mandatory. The LLM-judge quote must be an exact substring, or it is downgraded |
| Does decomposition help? | Assumed in draft | Literature (MiniCheck) says not consistently. **Ablation required.** The justification is explainability |

### A.2 Research and Evaluation Scientist

| Challenge | Finding | Revision |
|---|---|---|
| Representative data? | Legacy contexts have a median of 6 words. Real chunks are 100s of tokens | `gg-claims-v2` mandates 50–400-word contexts and multi-claim answers. Legacy is regression-only |
| Leakage? | Duplicates across any random split. Oracle evidence as input | **Group split by `context_group`**. Production-path inputs for headline numbers |
| Metrics appropriate? | Accuracy on an imbalanced, constructed distribution | Per-class P/R/F1, FAR/FRR, and macro-F1. Construction distribution is disclosed. Bootstrap CIs |
| Calibrated thresholds? | v0.1.0 threshold 0.70 chosen on the same data it is reported on | Thresholds/calibrators fit on dev only. Reported on test |
| Reproducible? | No manifests | Run manifests with hashes. Deterministic default chain |
| False acceptance measured how? | Gold "reliable" was implicit | Defined explicitly in methodology: an answer is *bad* if any assertive claim is CONTRADICTED or NOT_ENOUGH_INFO, or relevance fails, or a safety finding is present under the policy |
| Annotation quality? | One annotator. 4/16 noisy partial labels | Annotation guide v2 with a completeness dimension, label-correction audit log, second-annotator agreement (Cohen's κ) when available |

### A.3 Engineering Hiring Manager

| Challenge | Finding | Revision |
|---|---|---|
| Depth or breadth? | The draft's agents + dashboard scope risked a shallow core | M1–M4 are defined as **the** core deliverable. M5+ are gated on M4 results |
| Maintainable? | 2,300 lines of benchmark-fitted regex in the hot path | Moved behind `structured_facts` with declared scope. Not extended further. Replaced by general guards |
| Trade-offs documented? | Implicit | ADRs in `TECHNICAL_DECISIONS.md`, one per decision, with rejected alternatives |
| Ownership shown? | Risk of rewriting history to look better | v0.1.0 numbers are preserved and corrected **in the open**, with an audit trail |
| Reproducible by another engineer? | Required pip install + undocumented test inputs | `make bench` / `groundguard bench run` from a clean clone, documented in README |
