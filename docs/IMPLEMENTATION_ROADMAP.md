# GroundGuard V2 — Implementation Roadmap

**Status:** DRAFT, proposed. Each milestone ends with a report covering what is
complete, what was measured, and what remains. The owner reviews each report
before the next milestone starts.

**Order rule:** M1 → M4 are the core deliverable. M5+ start only after the M4
report exists, so a shallow agent/dashboard layer is never built on an
unmeasured core.

**Working rules (all milestones):**
- Preserve v0.1.0 behavior (`engine="v1"`) and keep the equivalence suite green.
- Never weaken or skip a test. A vacuous test is replaced by a *stronger* one.
- Never edit a benchmark label without an audit-log entry.
- No new runtime dependency in the core without an ADR.
- Commits are authored as Abualgasim Ibrahim. There are no AI co-author
  trailers. Nothing is pushed without owner approval.

---

## M0 — Specification ✅ (this document set)

Deliverables: `GROUNDGUARD_V2.md`, `ARCHITECTURE_V2.md`,
`EVALUATION_METHODOLOGY.md`, `IMPLEMENTATION_ROADMAP.md`,
`TECHNICAL_DECISIONS.md`.
Exit: owner approval.

## M1 — Benchmark integrity and harness

**Objective:** make every number reproducible by command, and publish the
honest v0.1.0 baseline.

| Area | Work |
|---|---|
| `groundguard/bench/datasets.py` | load legacy files in the order the existing tests use. Schema-validate against `benchmark/schema.json`. sha256. Dedup view. `context_group` assignment (exact context match + Jaccard near-dup) |
| `groundguard/bench/metrics.py` | confusion matrix, P/R/F1, macro-F1, FAR/FRR, group bootstrap CI, Wilson interval, threshold sweep. **Reuse** `evaluation/decision_metrics.evaluate_threshold` semantics, and test that they agree |
| `groundguard/bench/manifest.py`, `runner.py`, `compare.py` | run manifest. v1-engine runner. Paired deltas + per-record flips + tolerance rules |
| `groundguard/cli.py` + `[project.scripts]` | `groundguard bench run`, `groundguard bench compare` |
| `benchmarks/datasets/gg-legacy-v1/1.0.0/` | registry entry pointing to the existing `benchmark/` files (not copied, so history is preserved) + `DATASHEET.md` |
| `benchmarks/results/` | `v0.1.0-baseline.context.json`, `v0.1.0-baseline.oracle.json`, each in raw and dedup views |
| tests | Replace `assert correct >= 0` (relevance) and the grounding test without a bound with **regression assertions against the committed baseline** (exact for deterministic engines). Add metric unit tests (hand-computed fixtures), bootstrap determinism test, and manifest test |
| cleanup | remove dead `_propositions_conflict` (unreferenced. Undefined name `evidence`) |
| `README.md` | replace the benchmark section with reproduced numbers, oracle vs context, dedup, and a link to run files. The old numbers stay, labeled with how they were produced |
| tooling | `.github/workflows/ci.yml` (pytest + bench regression on legacy). `pyproject` extras `api`, `dev` |

**Exit criteria:** a clean clone runs `pip install -e .[dev] && pytest &&
groundguard bench run --dataset gg-legacy-v1`, which reproduces the committed
baseline hash. README numbers match run files.

## M2 — Claim-level pipeline and guards

**Objective:** per-claim verdicts with evidence spans, and closing the
negation/qualifier false-accept class.

| Area | Work |
|---|---|
| `core/` | types, errors, serialization, config hashing |
| `claims/` | segmenter with offsets. Assertiveness tagging |
| `evidence/` | sentence-window chunking, BM25 |
| `verifiers/` | `base` (protocol + chain), `lexical` (v1 adapter), `structured_facts` (v1 adapter with declared scope), `guards` (negation, number/unit, date, qualifier) |
| `pipeline.py` | orchestration. Derived v1-compatible labels |
| `api/v2.py` | `POST /v2/evaluate` (no auth yet. Local-only flag) |
| app factory | stop creating the store at import time. v1 routes unchanged (snapshot tests first) |
| tests | segmenter offset property tests. Each guard table-driven. **Probe suite** (`tests/probes/`) including the four audit probes. v1 equivalence over 250 records. Ablation runs (sentence/clause/conjunct) as bench configs |

**Exit criteria:** probe suite has 0 false accepts. The equivalence suite is
green. A legacy-dev report compares v1 vs v2-deterministic (with CIs), and
any v2 losses are explained.

## M3 — Policy engine

| Area | Work |
|---|---|
| `policy/` | model, TOML loader (closed condition set), engine with fired-rule trace |
| builtins | `v1_compat.toml`, `default_v2.toml`, `strict.toml` |
| integration | pipeline returns `DecisionResult`. `/v2/evaluate?policy=`. Manifest includes the policy hash |
| tests | loader rejects unknown conditions/decisions. Rule-order tests. **`v1_compat` reproduces v0.1.0 `system_decision` and `reason` on all 250 records.** HUMAN_REVIEW band tests |

**Exit criteria:** equivalence holds, and `default_v2` FAR/FRR on legacy-dedup
is reported.

## M4 — Held-out dataset, calibration, optional NLI

| Area | Work |
|---|---|
| dataset | `gg-claims-v2@1.0.0` per methodology §5 (construction scripts, LLM-generated answers with recorded model/prompt, annotation in JSONL), group split, frozen test, datasheet |
| labels | `gg-legacy-v1@1.1.0` corrections with audit log |
| `calibration/` | isotonic + Platt (pure Python), ECE/Brier, reliability-diagram data |
| `verifiers/nli.py` | `[nli]` extra. Pinned model revision. Batched inference. Latency measured |
| `verifiers/llm_judge.py` | `[llm]` extra, provider-agnostic interface. Prompt in repo with version. Quote-must-match guard. Repeated-run variance |
| reports | `docs/reports/M4_EVALUATION.md`: dev tuning log, single test run per chain, CIs, error analysis, OOD table if external data was reachable |

**Exit criteria:** a test-split report exists for the deterministic chain and
(if built) the NLI chain. The HUMAN_REVIEW operating point is chosen on dev
and reported on test.

**Dependency on the owner:** second-annotator availability (agreement
measurement). Decision on which domains to source public text from.

## M5 — RAG evaluation

Multi-source `contexts[]` with ids. Citation parsing (`[1]`, `[doc-3]`,
footnote styles, configurable regex). `citations.py`. `rag_metrics.py`
(faithfulness, utilization, reference-based precision/recall). Injection check
on every source. `gg-rag-v2` dataset. Report.

## M6 — Agent trace evaluation

`agents/` trace model, JSON-Schema-subset validator, six deterministic checks
plus reference-based tool-selection. Trace-scoped policy conditions.
`POST /v2/traces/evaluate`. `gg-agent-v1` fixtures (30–50). Report with
per-check P/R.

## M7 — Developer infrastructure and security

API keys (hashed, prefix lookup, constant-time compare), tenant scoping, token
bucket, payload caps, error envelope. Storage migrations + `evaluations_v2` +
SQL stats. `POST /v2/evaluate/batch`. `sdk/client.py`. `groundguard eval
--input`. CI regression-gate example workflow (`examples/ci/`). Integration
examples (plain Python RAG loop, FastAPI middleware pattern). Docker non-root
+ healthcheck. Security tests (auth bypass, oversize payload, filter
injection).

## M8 — Dashboard

Static HTML/CSS/JS served by the API, no CDN. Overview, evaluations, **claim
inspector**, benchmarks, compare/regression, configuration, API docs. Every
displayed number is sourced from storage or run files. Playwright screenshot
tests at desktop and mobile widths. Accessibility check (contrast, keyboard,
non-color verdict cues).

## M9 — Validation and release

Latency/throughput benchmark script with a hardware profile. The final
evaluation report collects all milestone results. README rewritten around
reproducible commands. `CHANGELOG.md`. Version 2.0.0 is tagged **only after
owner review**.

---

## Milestone report template

```
## Mx report
Objective:
Components changed:
Approach (and alternatives rejected → ADR links):
Tests added / changed (none weakened):
Full test suite: <passed>/<total>
Benchmark runs: <run ids>, with dataset hashes
Results vs previous baseline (with CIs):
Known regressions and why accepted:
Limitations discovered:
Remaining work:
```
