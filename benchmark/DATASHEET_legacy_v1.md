# Datasheet — `gg-legacy-v1@1.0.0`

**Role: regression only.** The v0.1.0 rules were developed and iterated
against these records, so results on this dataset are development-set results.
They must not be cited as evidence of generalization.

## Identity

| Field | Value |
|---|---|
| Dataset id | `gg-legacy-v1` |
| Version | `1.0.0` (records unchanged from v0.1.0) |
| Files | `benchmark/examples/human_labeled_001_020.json`, `benchmark/batch_001_021_030.json`, `benchmark/examples/batch_001_031_040.json` … `batch_001_241_250.json` (load order defined in `groundguard/bench/datasets.py`) |
| sha256 (file names + bytes, in load order) | `b455b7d46d54bbfb6af3949ce84e5fa551dedfccc3ebcebf77db9c7e1ec47e79` |
| Schema | `benchmark/schema.json` |
| Loader | `groundguard.bench.datasets.load_legacy_v1()` |

Not included: `benchmark/examples/{benchmark_001,contradiction,generated_examples,label_interactions,relevance}.json`
(small fixtures used by unit tests) and `benchmark/safety/*` (safety sets).

## Composition (measured)

| Property | Value |
|---|---|
| Records | 250 |
| Unique (question, context, answer) triples | **99** (70 singletons, 23 triples × 6 copies, 6 triples × 7 copies) |
| Unique contexts / context groups | 68 / 68 |
| Source field | synthetic 210, manual_annotation 20, public_text 20 |
| Annotators | 1 (`gasim`). All `LABELED`. Agreement not measured |
| Median context length | 6 words (max 30) |
| Answers with more than one sentence | 1 |
| Grounding labels | UNSUPPORTED 130, SUPPORTED 82, PARTIALLY_SUPPORTED 38 |
| Relevance labels | RELEVANT 207, IRRELEVANT 43 |
| Contradiction labels | NOT_CONTRADICTORY 189, CONTRADICTORY 61 |

The construction targets in `benchmark/manifest.json` (125 synthetic / 125
public text, 50/35/35 grounding mix) were not met. The repetition comes from
`scripts/generate_benchmark.py`, which emits the same case templates in several
batches.

## Known label issues (to be corrected in `@1.1.0` with an audit log)

| Record | Label | Issue |
|---|---|---|
| `synthetic_075` | PARTIALLY_SUPPORTED | answer is fully supported but omits information. That is completeness, not grounding |
| `synthetic_077` | PARTIALLY_SUPPORTED | same: "Supported claim omits the available date" |
| `public_056` | PARTIALLY_SUPPORTED | annotation note says "Both claims are supported by the source" |
| `public_065` | PARTIALLY_SUPPORTED | annotation note says "otherwise this should be SUPPORTED" |

These are 4 of the 16 unique PARTIALLY_SUPPORTED records. The labels are
**not** changed in `1.0.0`, so the v0.1.0 baseline stays reproducible.

## Splits

`groundguard.bench.datasets.group_split` assigns whole context groups to
dev/test by hash (109 dev / 141 test records at `test_fraction=0.4`). Every
record in this dataset has already been seen during rule development, so this
split exists only to exercise the mechanism. It carries no held-out meaning.

## Statistical power

Records within a context group are correlated (duplicates and paraphrases of
one context), so group bootstrap intervals are wide. With 68 groups, the
95% interval for decision FAR on the full dataset is 0.0%–15.0%. Treat all
differences smaller than that as noise.

## Reproduced v0.1.0 baseline

See `benchmark/results/v0.1.0-baseline.{context,oracle,oracle_no_question}.json`
and the README benchmark section.
