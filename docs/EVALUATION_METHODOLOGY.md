# GroundGuard — Evaluation Methodology (V2)

**Status:** DRAFT, proposed. Supersedes nothing yet.
`docs/evaluation_specification.md` and `docs/annotation_guidelines.md` remain
the v1 references until M4.

This document defines **what is measured, on which data, how, and what may be
claimed from it.**

---

## 1. Principles

1. **Measure decisions, not just scores.** The primary quantity is the
   false-accept rate of the deployed policy.
2. **The input is what production sees.** Headline numbers use the `context`
   the API receives, never annotator-selected evidence.
3. **Held-out means held-out.** Rules, thresholds, and calibrators are fit on
   dev. Test is looked at only to report, and every look is logged.
4. **Unique items, grouped splits.** Duplicates are removed before metrics.
   Splits are by context group, so a context never appears in both dev and test.
5. **Uncertainty is reported.** Every rate comes with a 95% bootstrap CI and its
   denominator.
6. **An LLM judge is a system under test.** It is never ground truth and never
   labels test data.
7. **Corrections are public.** Label changes are recorded in an audit log with
   the old label, new label, reason, and date.

## 2. Status of v0.1.0 results

Reproduced on 2026-11-05 by running the repository code on the repository
benchmark files (no modifications). These are **development-set** numbers:
the rules were iterated against the same records.

| Metric | Records | Input | Result |
|---|---|---|---|
| Grounding accuracy | 250 (with duplicates) | context | 64.4% (161/250) |
| Grounding accuracy | 99 unique | context | 59.6% (59/99) |
| Relevance accuracy | 250 / 99 unique | — | 97.2% / 98.0% |
| Contradiction accuracy | 250 | **gold evidence (oracle)** | 99.2% (248/250), the README figure |
| Contradiction accuracy | 250 | context | 98.0% (245/250) |
| Contradiction accuracy | 99 unique | context | 94.9% (94/99). Recall on CONTRADICTORY 20/25, 0 FP |
| Grounding / contradiction | 20 public_text only | context | 50% / 85% |
| End-to-end decision, gold reliable = SUPPORTED ∧ RELEVANT ∧ NOT_CONTRADICTORY | 250 | context | FAR 8/168 (4.8%), FRR 50/82 (61.0%) |

M1 committed these as `benchmark/results/v0.1.0-baseline.{context,oracle,oracle_no_question}.json`,
so they are reproducible by command (`groundguard bench run`) rather than by
prose, and `tests/test_bench_baseline.py` pins them. Group-bootstrap 95%
intervals over the 68 context groups are wide (e.g. FAR 0.0–15.0% on all 250
records), so differences smaller than that are noise on this dataset.

The v0.1.0 README threshold table (FAR 7.74% / FRR 62.20% at 0.70) does not
match the current code (6.55% / 60.98% in `oracle_no_question` mode). It was
generated before commit `491b85c` changed the contradiction code and was not
regenerated, because `tests/test_threshold_analysis.py` prints but never asserts.

## 3. Units of evaluation and labels

### 3.1 Claim level (new)

A **claim** is a minimal assertive statement that can be checked independently
against the sources. Annotators label each claim:

| Label | Definition | Example (context: "Refunds are available within 30 days, except for digital goods.") |
|---|---|---|
| `SUPPORTED` | the sources entail the claim. A reasonable reader needs no outside knowledge | "Physical items can be refunded within 30 days." |
| `CONTRADICTED` | the sources entail the claim's negation, or state an incompatible value for the same attribute of the same entity and scope | "Digital goods can be refunded within 30 days." |
| `NOT_ENOUGH_INFO` | neither entailed nor contradicted | "Refunds are processed within 5 business days." |

Rules:
- **Scope and qualifiers matter.** "approved for adults" does not support
  "approved for children". It *contradicts* only if the source makes the
  restriction exclusive ("only adults"). Otherwise it is NOT_ENOUGH_INFO.
- **Numbers:** an approximate value is SUPPORTED only when the source is
  approximate in the same direction ("about 78%" vs "78%" is SUPPORTED, "80%"
  vs "78%" is CONTRADICTED).
- **Additive facts:** "sells A" with a source saying "sells B" is
  NOT_ENOUGH_INFO unless the source claims exhaustiveness ("sells only B", "its
  two products are…"). This replaces the v1 question-aware rule, which inferred
  exhaustiveness from the question wording.
- **Non-assertive text** (questions, hedges, meta-statements) is not a claim.

### 3.2 Answer level

Derived from claim labels (see GROUNDGUARD_V2.md §7) plus two independent
dimensions:

- **Relevance:** `RELEVANT` / `IRRELEVANT`. Does the answer address the question asked?
- **Completeness (new):** `COMPLETE` / `INCOMPLETE` / `NOT_ASSESSED`. Does the
  answer include the information in the sources that the question asks for?
  This is where v1 cases like `synthetic_077` ("launched a platform", with the
  year omitted) belong. **Completeness is not grounding.**

### 3.3 "Bad answer" for decision metrics

For FAR/FRR, the *gold* acceptability of an answer under the default policy is:

```
bad(answer) = any assertive claim is CONTRADICTED
           or any assertive claim is NOT_ENOUGH_INFO
           or relevance == IRRELEVANT
           or a safety finding exists (PII in output, injection in output)
good(answer) = not bad(answer)
```

The definition is versioned (`acceptability@1`). Policies that tolerate
NOT_ENOUGH_INFO (e.g. FLAG instead of REJECT) are evaluated under the
corresponding definition, and the report states which one was used.

## 4. Metrics

| Metric | Formula | Level |
|---|---|---|
| **FAR** (false-accept rate) | ACCEPTed bad answers / all bad answers | decision, **primary** |
| **FRR** (false-reject rate) | non-ACCEPTed good answers / all good answers | decision |
| Review rate | HUMAN_REVIEW / all | decision |
| FAR among auto-decided | ACCEPTed bad / (bad that were not routed to HUMAN_REVIEW) | decision, shows the effect of abstention |
| Precision / recall / F1 per label | standard, one-vs-rest | claim and answer |
| Macro-F1 | mean per-label F1 | claim and answer |
| CONTRADICTED recall | reported separately, as it is the costliest miss | claim |
| Confusion matrix | full 3×3 (claim) / 3×3 grounding / 2×2 relevance | all |
| ECE | Σ_b (n_b/N)·\|acc_b − conf_b\|, 10 equal-mass bins | only for calibrated verifiers |
| Brier score | mean (p − y)² | calibrated verifiers |
| Threshold sweep | FAR/FRR at each threshold on **dev**. The chosen operating point is reported on test | decision |
| Citation precision / recall | see GROUNDGUARD_V2.md §10 | RAG |
| Latency | p50 / p95 / p99 per stage and end-to-end, warm, with hardware profile | system |
| Throughput | evaluations/s single process, fixed input size distribution | system |

**Confidence intervals:** non-parametric bootstrap over *context groups* (not
records, because records within a group are correlated). 2,000 resamples,
fixed seed, 2.5/97.5 percentiles. For rates with a denominator below 30, the
Wilson interval is also reported.

**Comparisons between runs:** paired bootstrap over the same items. A
regression is declared when the 95% CI of the delta excludes zero in the bad
direction, **or** when a configured absolute tolerance is exceeded (e.g.
`far > +0.01`). The tolerance rule is used for small datasets where the CI is
uninformative.

## 5. Datasets

### 5.1 Construction requirements for `gg-claims-v2`

| Property | Requirement |
|---|---|
| Size | ≥ 300 answers and ≥ 900 claims at v1.0. Test ≈ 40% by context group |
| Context length | 50–400 words. ≥ 30% multi-paragraph. ≥ 20% multi-source |
| Domains | ≥ 6 (e.g. policies/support, product docs, finance filings, health information leaflets, public science pages, software documentation) |
| Phenomena (each ≥ 5% of claims) | negation, qualifier/scope, numeric with units, dates/temporal order, paraphrase/synonymy, coreference, list exhaustiveness, entity confusion |
| Answer sources | ≥ 50% generated by real LLMs given the context (model + prompt recorded), the rest hand-perturbed for targeted phenomena |
| Provenance | public-text rules from `public_text_sourcing_policy.md` (URL, publisher, retrieval date, license note) |
| Grouping | `context_group` id. All answers about the same source passage share it |
| Datasheet | `DATASHEET.md` per version (motivation, composition, collection, labeling, known issues) |

### 5.2 Splits and leakage controls

- Split by `context_group` with a fixed seed. The split file is committed and hashed.
- Near-duplicate detection before splitting: normalized-text MinHash or
  Jaccard ≥ 0.8 over 5-gram shingles (pure Python). Near-duplicates are forced
  into the same group.
- The **test split is frozen** at dataset release. Changes require a new
  dataset version, and results across versions are never compared directly.
- `TEST_ACCESS_LOG.jsonl` records every test-split run (run id, date, purpose).
  CI never runs on test.

### 5.3 Legacy dataset

`gg-legacy-v1@1.0.0` is the 250 v0.1.0 records, unchanged. Reported both raw
and deduplicated (99). Because the rules were fit to it, **it is used only for
regression and must never be cited as a generalization result.**
`@1.1.0` applies label corrections (starting with `synthetic_075`,
`synthetic_077`, `public_056`, `public_065`) with an audit log, and it moves
completeness into its own field.

### 5.4 External data (optional, M4+)

Candidate out-of-distribution sets: LLM-AggreFact (Tang et al., 2024:
aggregates 10 human-labeled grounded-factuality datasets, sentence-level
labels) and RAGTruth (Niu et al., ACL 2024: ~18k RAG responses with word-level
hallucination annotations). They are used through download scripts after a
license check, never vendored, and reported as separate tables. Label mapping
is documented: both are binary supported/unsupported, so they cannot measure
the CONTRADICTED vs NOT_ENOUGH_INFO distinction.

## 6. Annotation protocol (v2)

1. Read the question, all sources, and the answer.
2. Segment the answer into claims using the guide's examples (or confirm the
   automatic segmentation, recording edits).
3. Label each claim and **quote the evidence span** (exact substring, with
   source id) for SUPPORTED / CONTRADICTED.
4. Label relevance and completeness.
5. Mark `uncertain=true` with a reason instead of guessing.
6. **Agreement:** a second annotator independently labels ≥ 20–30% of the test
   split. Report Cohen's κ per dimension, then adjudicate disagreements and log
   them. *Requires the owner to arrange a second annotator. If unavailable,
   the report states "single annotator, agreement not measured".*
7. LLM assistance is permitted only for drafting segmentation, never for
   labels. Its use is recorded per record.

## 7. Calibration

- Calibrators are fit per `(verifier@version, predicted label)` on the dev
  split only, and only for pairs with at least 30 dev claims (configurable).
  Other pairs stay uncalibrated. Isotonic regression is used by default and
  Platt scaling when dev has fewer than 200 claims.
- The output is **P(the verdict is correct | raw score)**. *Revised in M4a.*
  The earlier plan was one-vs-rest label probabilities, but raw scores mean
  different things per verifier and label (coverage is evidence for
  SUPPORTED and against NOT_ENOUGH_INFO), and correctness is what the
  `min_confidence_below` policy condition needs (ADR-020).
- Fitting refuses test-split runs (`groundguard calibrate fit`).
- ECE, Brier score, and a reliability diagram are reported on test.
- A changed verifier invalidates its calibrator. `confidence = None` until
  refit. The UI displays "uncalibrated".
- The HUMAN_REVIEW band (e.g. calibrated confidence in [0.4, 0.6]) is chosen on
  dev to hit a target review rate, and its FAR-among-auto-decided is reported
  on test.

## 7a. Claim-level and answer-level measurement (gg-claims-v2)

`groundguard bench claims` reports two levels separately (ADR-021):

- **Claim level, oracle segmentation.** Each gold claim is verified directly,
  which isolates verifier quality from segmentation. It reports accuracy,
  per-label P/R/F1, the 3×3 confusion matrix, per-phenomenon accuracy and
  CONTRADICTED recall, and **evidence localization**: on correctly labelled
  SUPPORTED/CONTRADICTED claims, whether the cited evidence overlaps the
  annotator's quote.
- **Answer level, end to end.** The full pipeline (segmentation,
  verification, policy) is scored with acceptability@1. Safety is not
  included, because gg-claims-v2 has no safety labels.

Segmentation quality itself is not yet measured. A span-agreement metric
between system and gold claims is future work.

## 8. Error analysis procedure

For each milestone report:

1. All false accepts on dev, categorized by phenomenon (negation, qualifier,
   number, paraphrase, segmentation error, evidence-selection miss, verifier
   miss).
2. A sample of 30 false rejects with the same taxonomy.
3. **Attribution:** for each error, which stage was wrong (segmenter, evidence
   selection, guard, backend, policy). This works because stages are logged
   separately.
4. Fixes are developed against dev. The test number is reported once per
   milestone.

## 9. Safety evaluation

| Detector | Dataset | Metrics | Notes |
|---|---|---|---|
| PII | `gg-safety-v2/pii`: positives per category, hard negatives (order numbers, Luhn-invalid 16-digit strings, version strings that look like IPs), multilingual formats | per-category P/R, span-level exact match | regex limits are stated. Names/addresses are out of scope without an optional backend |
| Prompt injection (output) | direct injections, benign texts that mention "instructions" | P/R, FPR on benign | |
| Prompt injection (indirect) | injections embedded in otherwise relevant retrieved chunks | detection rate per source, FPR on clean chunks | new in v2 |

The v0.1.0 safety sets (20 PII, 16 injection) were written alongside the
detectors and are kept as regression only.

## 10. Agent evaluation

`gg-agent-v1`: 30–50 hand-built traces, each with a fault label set drawn from
{`invalid_args`, `disallowed_tool`, `redundant_calls`, `ignored_error`,
`state_contradiction`, `ungrounded_final`, `none`}. Reported per check:
precision and recall on the fault it targets, plus the trace-level decision
FAR/FRR. These traces are synthetic by construction, and reports say so.

## 11. Reporting template

Every published result states: dataset id@version and sha256, split, record
and group counts, input mode (context vs oracle), engine and verifier chain,
policy id@version, acceptability definition version, metric values with 95%
CI and denominators, git SHA, and date. Any number missing these fields is not
published.

## 12. Known limitations (standing)

- Evaluation is relative to the supplied sources. Correct-but-unsourced claims
  are NOT_ENOUGH_INFO by design.
- Constructed datasets do not reflect production class frequencies. FAR at
  deployment depends on the deployment's base rate of bad answers.
- Deterministic verifiers do not understand paraphrase well. This is the
  measured motivation for the optional NLI backend, not an assumption.
- Single-annotator labels unless a second annotator is arranged.
