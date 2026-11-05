# GroundGuard — Technical Decisions (ADR log)

Format: lightweight ADRs. Each decision lists the context, the decision,
rejected alternatives, and consequences. Status values are `Proposed`,
`Accepted`, and `Superseded by ADR-x`. All are **Proposed** pending owner
review of the V2 specification.

---

## ADR-001 — Fix measurement credibility before adding features
**Context.** Independent reproduction (GROUNDGUARD_V2.md §5.2) found that
published v0.1.0 results depend on duplicated records (99 unique of 250), use
oracle evidence for the contradiction headline, and were tuned on the
reporting set.
**Decision.** M1 builds the benchmark harness and republishes honest baselines
before any new evaluator work.
**Rejected.** (a) Improve grounding first, which would mean measuring
improvement with the same flawed yardstick. (b) Silently replace README
numbers, which would hide a methodology change.
**Consequences.** Headline numbers will go down. The old numbers are retained
with a description of how they were produced.

## ADR-002 — Three-way claim verdicts; completeness is a separate dimension
**Context.** v1 has answer-level grounding labels, and some
PARTIALLY_SUPPORTED labels encode *incompleteness* (`synthetic_077`).
**Decision.** Claims are labeled SUPPORTED / CONTRADICTED / NOT_ENOUGH_INFO.
Answer grounding labels are derived. Completeness is its own optional
dimension.
**Rejected.** Binary supported/unsupported (as in LLM-AggreFact, RAGTruth),
because it loses the "unsupported ≠ contradicted" principle, which is v1's
strongest idea. A graded 5-point scale was also rejected because it is not
annotatable reliably by one person.
**Consequences.** External binary datasets cannot evaluate the
CONTRADICTED/NEI split. This is reported as a limitation.

## ADR-003 — Deterministic default chain; model-backed verifiers are optional extras
**Context.** Reproducibility and zero-dependency install are v1 strengths.
Token overlap cannot handle paraphrase.
**Decision.** Default chain is `guards → structured_facts → lexical`, all
stdlib. `nli` and `llm_judge` ship as extras behind the same `Verifier`
protocol and are measured on the same datasets.
**Rejected.** (a) Make an LLM judge the default, which brings
nondeterminism, cost, data egress, and judge-as-truth risk. (b) Heavy
dependencies such as spaCy, transformers, or sentence-transformers in core,
which costs install size and cold start.
**Consequences.** Default-chain paraphrase recall stays limited, and the
report says so. Teams that need better recall opt into `[nli]` with measured
latency.

## ADR-004 — Keep v1 in place; reach it via `engine="v1"` with an equivalence test
**Context.** Existing API users and 224 tests depend on v1 semantics.
**Decision.** `groundguard/domain`, `application`, `evaluation` stay where
they are, unchanged. v2 adapts them through `verifiers/lexical`,
`verifiers/structured_facts`, and `checks/relevance`. An equivalence test
pins v1 outputs on all 250 legacy records.
**Rejected.** Move to `legacy/` (import churn, no benefit). Rewrite in place
(silent semantic change).
**Consequences.** Some duplication (e.g. three copies of `NUMBER_WORDS` in
v1) remains in v1 code. New code does not copy it.

## ADR-005 — Freeze the proposition engine; do not extend it
**Context.** `propositions.py` + `proposition_comparison.py` + `contradiction.py`
(~2,300 lines) cover 18 predicates and were extended to fit specific benchmark
records.
**Decision.** Wrap it as `structured_facts` with a declared predicate scope.
It abstains outside that scope. No new predicates. General contradiction
detection moves to guards (negation/number/date/qualifier) plus optional NLI.
**Rejected.** Grow the regex vocabulary. Each predicate fixes benchmark cases
and does not generalize.
**Consequences.** On legacy data, contradiction may drop slightly when
structured_facts abstains where it used to guess. This is measured and
reported in M2.

## ADR-006 — Group-based splits and a test-access log
**Context.** Duplicated templates make random splits leak.
**Decision.** Split by `context_group` (exact + near-duplicate clustering).
The test split is frozen per dataset version. Every test run is appended to
`TEST_ACCESS_LOG.jsonl`.
**Rejected.** k-fold cross-validation on legacy data. It is too small and
duplicated, and it encourages tuning on everything.
**Consequences.** Fewer, slower test reads, which is intentional.

## ADR-007 — Primary metric is FAR at the configured policy, with CIs
**Context.** Accuracy on a constructed distribution says little about deployment risk.
**Decision.** Report decision-level FAR (and FRR, review rate) with group
bootstrap 95% CIs and denominators. Component metrics are diagnostic.
**Rejected.** A single composite "reliability score" as the headline. It hides
the trade-off v1's own threshold table exposed.
**Consequences.** Results depend on the acceptability definition, which is
therefore versioned (`acceptability@1`).

## ADR-008 — Declarative TOML policies with a closed condition vocabulary
**Status.** Accepted, implemented in M3 (`groundguard/policy/`).
**Context.** Decision rules are hard-coded in `domain/decision.py`.
**Decision.** Policies are TOML parsed with stdlib `tomllib`. Rules are
ordered, the first terminal rule wins, and conditions come from a fixed,
validated set. `v1-compat.toml` must reproduce v1 decisions exactly; it
does, on all 250 legacy records and 31 probes (decisions only; reason texts
are not reproduced).
**Rejected.** (a) YAML, which adds a dependency. (b) A Python-expression DSL
or `eval`, which is an injection risk and hard to audit. (c) Rego/CEL, which
is heavyweight for this scope.
**Consequences.** New condition kinds require code and tests. This is
intentional, so every condition is documented.

## ADR-009 — Modular monolith on SQLite
**Context.** The workload is single-tenant to small multi-tenant, and
evaluation is CPU-bound and short.
**Decision.** One package, one optional FastAPI process, and SQLite with
migrations and indexed columns. SQL aggregation for stats. App factory with
lifespan instead of an import-time store.
**Rejected.** Microservices, task queues, and Postgres-by-default, because no
measured requirement exists.
**Consequences.** Rate limiting is per-process. Multi-replica needs an
external limiter and Postgres. Documented as deferred.

## ADR-010 — Defer webhooks and async batch jobs
**Context.** The mission brief lists webhooks "where useful".
**Decision.** Not in v2. Synchronous batch with a size cap covers CI and
offline use.
**Rejected.** Webhook delivery with retries and signing. That is real
complexity without a consumer.
**Consequences.** Revisit when a user needs push notifications on regression.

## ADR-011 — LLM judge contract
**Context.** Judges are useful but fallible and nondeterministic.
**Decision.** The judge prompt is versioned in-repo. The output must match a
JSON schema. The quoted evidence must be an exact substring of a supplied
candidate, otherwise the verdict becomes NOT_ENOUGH_INFO. Model id, prompt
version, temperature, and seed (if supported) go into the manifest.
Repeated-run variance is reported. Judges never label benchmark data.
**Rejected.** Free-text judge rationales as evidence.
**Consequences.** The judge can only cite what was supplied, which limits
hallucinated justifications.

## ADR-012 — Injection checks cover retrieved sources
**Context.** v1 scans only the answer. In RAG, the primary vector is
instructions embedded in retrieved content (indirect injection).
**Decision.** Run the injection detector on the answer and on every
`SourceDocument`, reporting the location. Policy can route source-level
findings to HUMAN_REVIEW.
**Rejected.** Claiming injection *prevention*. GroundGuard is post-hoc and
pattern-based.
**Consequences.** More findings (and false positives on documents that discuss
prompt injection). FPR is measured on clean chunks.

## ADR-013 — Claim decomposition is justified by explainability, and its accuracy effect is measured
**Context.** MiniCheck (Tang et al., EMNLP 2024) reports that explicit claim
decomposition did not consistently improve fact-checking accuracy.
**Decision.** Decompose deterministically for localization and explanation.
Run sentence/clause/conjunct ablations and report the effect. The default
granularity is chosen on dev.
**Rejected.** Assuming decomposition improves accuracy. LLM-based
decomposition by default, because of nondeterminism.
**Consequences.** The default granularity may end up coarser than the UI's
display granularity.

## ADR-014 — Stdlib-only property and statistics code
**Context.** Avoid dependencies in core and test tooling.
**Decision.** BM25, isotonic/Platt calibration, bootstrap, Wilson intervals,
MinHash/Jaccard, and randomized property tests (fixed seeds) are implemented
in pure Python. Each has unit tests against hand-computed values.
**Rejected.** numpy/scipy/scikit-learn/hypothesis in core.
**Consequences.** It is slower on very large datasets, which is acceptable at
current scales (≤ 10⁴ claims). Revisit if benchmarks exceed that.

## ADR-015 — Git authorship and history
**Context.** The repository owner is the engineering lead and owns all decisions.
**Decision.** Repository-local identity is `Abualgasim Ibrahim
<aboelgasimibrahim999@gmail.com>`, the same email as existing history. No AI
co-author trailers. No history rewriting. Nothing is pushed without explicit
owner approval.
**Consequences.** The session environment's default git identity is
overridden locally before the first commit.

## ADR-016 — Default coverage backend: content tokens at threshold 1.0
**Status.** Accepted (M2), to be re-validated on held-out data in M4.
**Context.** v1 scored support as token overlap including stop words, with
threshold 0.80. On short claims one uncovered key word still passes
("Orion Labs sells **accounting** software" against "sells project-management
software" scores 0.8).
**Decision.** The v2 lexical backend scores the fraction of *content* tokens
covered (stop and negation words removed, light stemming, canonical numbers)
and requires full coverage by default.
**Evidence (gg-legacy-v1, unique records, seen data).** content@1.0 gives FAR 2/61
and FRR 11/38. content@0.8 gives FAR 5/61 and FRR 7/38. v1-similarity@0.8 gives FAR 4/61 and FRR 11/38
(conjunct granularity, guards on). FAR is the primary metric (ADR-007).
**Consequences.** Synonyms and paraphrases are NOT_ENOUGH_INFO (false
rejects). The optional NLI backend (M4) exists for this. The threshold is
configurable per pipeline.

## ADR-017 — Multi-sentence evidence windows only for coreference
**Context.** Pooling tokens across adjacent sentences let claims borrow
support from unrelated neighbours.
**Decision.** A multi-sentence window is created only when each later
sentence opens with a referring word (it, they, this, ...).
**Consequences.** Claims whose support genuinely spans two non-anaphoric
sentences are NOT_ENOUGH_INFO. That is a false reject, not a false accept.

## ADR-018 — Structured facts are contradiction-only
**Context.** A matching v1 proposition does not cover content the extractor
ignored ("founded in 2018 by Jane Doe" matches "founded in 2018").
**Decision.** The structured-facts verifier only returns CONTRADICTED, for
single-valued predicates. Support is always decided by coverage.
**Consequences.** No false support from partial extraction. On gg-legacy-v1
(conjunct, content@1.0, guards on), contradiction recall is 43/61 with the
verifier and 23/61 without it (unique records: 18/25 vs 13/25), with no
false contradictions in either configuration.

## ADR-019 — HUMAN_REVIEW for non-exclusive qualifier mismatches
**Status.** Accepted (M3). The owner chose this option.
**Context.** A claim about a different population, period or scope than the
evidence ("approved for adults" vs a claim about children) is NOT_ENOUGH_INFO
under the methodology, not CONTRADICTED. Under the M2 rules it was FLAGged
like any unverifiable claim, which hides that it is a higher-risk kind.
**Decision.** The `default` policy (2.0.0) routes any claim whose guards fired
the `qualifier` signal to HUMAN_REVIEW. The rule comes after safety,
contradiction and relevance (those still REJECT), and before the support rules.
**Rejected.** REJECT, which treats an unproven mismatch like a contradiction
and increases false rejects for answers that are merely narrower than the
source. FLAG, which keeps M2 behavior but loses the risk distinction.
**Evidence.** On the probes, `qual_01_audit` and `qual_03` go to review, and
false accepts stay at 0/18. On gg-legacy-v1 no record triggers the rule, so
the review rate there is 0/250 and the policy's effect is untested on that
dataset. Measuring the review rate needs data with scope mismatches (M4).
**Consequences.** Deployments must be able to act on HUMAN_REVIEW. FAR is
reported both overall and among auto-decided answers. A good answer sent to
review counts as a false reject.
