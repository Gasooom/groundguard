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

## M1 — Benchmark integrity and harness ✅ (report at the end of this document)

**Objective:** make every number reproducible by command, and publish the
honest v0.1.0 baseline.

| Area | Work |
|---|---|
| `groundguard/bench/datasets.py` | load legacy files in the order the existing tests use. Schema-validate against `benchmark/schema.json`. sha256. Dedup view. `context_group` assignment (exact context match + Jaccard near-dup) |
| `groundguard/bench/metrics.py` | confusion matrix, P/R/F1, macro-F1, FAR/FRR, group bootstrap CI, Wilson interval, threshold sweep. **Reuse** `evaluation/decision_metrics.evaluate_threshold` semantics, and test that they agree |
| `groundguard/bench/manifest.py`, `runner.py`, `compare.py` | run manifest. v1-engine runner. Paired deltas + per-record flips + tolerance rules |
| `groundguard/cli.py` + `[project.scripts]` | `groundguard bench run`, `groundguard bench compare` |
| `benchmark/DATASHEET_legacy_v1.md` | dataset registered in code, pointing to the existing `benchmark/` files (not copied, so history is preserved) |
| `benchmark/results/` | `v0.1.0-baseline.{context,oracle,oracle_no_question}.json`. Each contains all / dedup / per-source views |
| tests | Replace `assert correct >= 0` (relevance) and the grounding test without a bound with **regression assertions against the committed baseline** (exact for deterministic engines). Add metric unit tests (hand-computed fixtures), bootstrap determinism test, and manifest test |
| cleanup | remove dead `_propositions_conflict` (unreferenced. Undefined name `evidence`) |
| `README.md` | replace the benchmark section with reproduced numbers, oracle vs context, dedup, and a link to run files. The old numbers stay, labeled with how they were produced |
| tooling | `.github/workflows/ci.yml` (pytest + bench regression on legacy). `pyproject` extras `api`, `dev` |

**Exit criteria:** a clean clone runs `pip install -e .[dev] && pytest &&
groundguard bench run --dataset gg-legacy-v1`, which reproduces the committed
baseline hash. README numbers match run files.

## M2 — Claim-level pipeline and guards ✅ (report at the end of this document)

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
| app factory | **moved to M7**: existing tests import `app` at module level, so the refactor belongs with the storage and auth work |
| tests | segmenter offset property tests. Each guard table-driven. **Probe suite** (`tests/probes/`) including the four audit probes. v1 equivalence over 250 records. Ablation runs (sentence/clause/conjunct) as bench configs |

**Exit criteria:** probe suite has 0 false accepts. The equivalence suite is
green. A legacy-dev report compares v1 vs v2-deterministic (with CIs), and
any v2 losses are explained.

## M3 — Policy engine ✅ (report at the end of this document)

| Area | Work |
|---|---|
| `policy/` | model, TOML loader (closed condition set), engine with fired-rule trace |
| builtins | `v1_compat.toml`, `default_v2.toml`, `strict.toml` |
| integration | pipeline returns `DecisionResult`. `/v2/evaluate?policy=`. Manifest includes the policy hash |
| tests | loader rejects unknown conditions/decisions. Rule-order tests. **`v1_compat` reproduces v0.1.0 `system_decision` and `reason` on all 250 records.** HUMAN_REVIEW band tests |

**Exit criteria:** equivalence holds, and `default_v2` FAR/FRR on legacy-dedup
is reported.

## M4 — Held-out dataset, calibration, optional NLI (M4a ✅ infrastructure; M4b pending review and data)

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

## M6 — Agent trace evaluation ✅ (deterministic checks; report at the end of this document)

`agents/` trace model, JSON-Schema-subset validator, six deterministic checks
plus reference-based tool-selection. Trace-scoped policy conditions.
`POST /v2/traces/evaluate`. `gg-agent-v1` fixtures (30–50). Report with
per-check P/R.

## M7 — Developer infrastructure and security

App factory with lifespan (no store creation at import time). API keys (hashed, prefix lookup, constant-time compare), tenant scoping, token
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

---

## M1 report

**Objective:** make every published number reproducible by command, and
publish the honest v0.1.0 baseline.

**Components changed:**
- New: `groundguard/bench/` (`datasets`, `metrics`, `runner`, `report`,
  `manifest`, `compare`, `errors`), `groundguard/cli.py`
  (`groundguard bench run|compare`), `benchmark/results/v0.1.0-baseline.*.json`,
  `benchmark/DATASHEET_legacy_v1.md`, `.github/workflows/ci.yml`.
- Changed: `pyproject.toml` (`api` extra, console script, explicit package
  discovery), three benchmark tests (assertions strengthened), README
  benchmark section.
- Removed: two unused helpers in `groundguard/domain/contradiction.py`.
  Behavior is unchanged, as proven by the exact baseline match.

**Approach.** The harness reads the existing benchmark files in place and does
not copy them. The input mode is explicit because it changes results:
`context` is the production path, `oracle` and `oracle_no_question` reproduce
what the v0.1.0 tests measured. Intervals are bootstrap over context groups,
because records are heavily duplicated. Standard library only (ADR-014).
Rejected alternatives: copying data into a new `benchmarks/` tree, which would
split history across two directories, and record-level bootstrap, which gives
falsely narrow intervals with duplicated records.

**Tests.** 226 → 268 passing. No test weakened, skipped, or deleted.
- `assert correct >= 0` (relevance, contradiction) and the unbounded grounding
  test now assert the reproduced counts.
- A new production-path contradiction test asserts 245/250.
- `test_bench_baseline.py` requires exact reproduction of committed predictions
  and metrics in all three modes, plus regression detection and CLI exit codes.
- Metric unit tests use hand-computed values and include an equivalence check
  with `evaluation.decision_metrics.evaluate_threshold`.

**Benchmark runs** (dataset sha256 `b455b7d4…`, generated from clean commit `bf58994`):

| Mode | predictions_hash | Grounding | Relevance | Contradiction | FAR | FRR |
|---|---|---|---|---|---|---|
| context, all 250 | `58223226…` | 161/250 | 243/250 | 245/250 | 8/168 | 50/82 |
| context, dedup 99 | — | 59/99 | 97/99 | 94/99 | 3/61 | 22/38 |
| oracle, all 250 | `e360af76…` | 161/250 | 243/250 | 248/250 | 8/168 | 50/82 |
| oracle_no_question, all 250 | `0091e112…` | 161/250 | 243/250 | 235/250 | 8/168 | 50/82 |

**Findings during M1:**
- The README threshold table was stale. It predates commit `491b85c`.
  Current code gives FAR 6.55% / FRR 60.98% at 0.70, not 7.74% / 62.20%.
  README now shows the reproduced table and explains the difference.
- The contradiction benchmark test was also vacuous (`>= 0`), so the published
  248/250 had never been enforced.
- With only 68 context groups, 95% intervals are wide (FAR 0.0–15.0%). The
  legacy dataset cannot distinguish small improvements, which is a further
  reason for `gg-claims-v2` in M4.

**Not verified locally:** the CI `docker build` step (no Docker daemon in the
development environment). The Dockerfile is unchanged from v0.1.0.

**Remaining (next: M2):** claim-level pipeline, negation/number/qualifier
guards with a probe suite, `/v2/evaluate`, and a v1 equivalence suite.

---

## M2 report

**Objective:** claim-level verdicts (SUPPORTED / CONTRADICTED /
NOT_ENOUGH_INFO) with evidence spans, and closing the negation / qualifier /
number / date false-accept class found in the audit.

**Components.** New: `groundguard/core` (types, errors, text, serialization),
`groundguard/claims` (segmenter, assertiveness), `groundguard/evidence`
(chunking, BM25), `groundguard/verifiers` (chain, guards, structured_facts,
lexical), `groundguard/pipeline.py`, `groundguard/api/v2.py`
(`POST /v2/evaluate`), v2 engine in `groundguard/bench`. Changed:
`groundguard/api/app.py` (one line mounts the v2 router), `pyproject.toml`
(mypy config), CI (mypy + v2 regression gate). **Unchanged:**
`groundguard/domain`, `application`, `evaluation`, `storage`. The v1
baseline still reproduces exactly.

**Process.** The probe suite (`tests/probes/probes.json`, 31 probes) was
committed (`34b6f71`) before any guard code existed. Defaults were chosen
by ablation and recorded in ADR-016 to ADR-018.

**Tests.** 268 → 427 passing, none weakened or skipped. mypy `--strict`
is clean on all new packages.

### Probe suite (behavior specification, not a benchmark)

| Engine | False accepts (of 18 must-not-accept) | False rejects (of 13 must-accept) | Contradiction expectations missed |
|---|---|---|---|
| v1 (`POST /evaluate`) | 9 | 8 | not measured |
| v2 default | **0** | 6 | 0 |

The six v2 failures are listed in `tests/test_probes.py::KNOWN_LIMITATIONS`:
three paraphrases (no deterministic synonym handling) and three caused by
the v1 relevance check that v2 reuses unchanged ("when" questions require a
year).

### gg-legacy-v1, production path (seen data: development results only)

| | v1 | v2 sentence | v2 clause | v2 conjunct (default) |
|---|---|---|---|---|
| Grounding acc., all 250 | 161 | 185 | 185 | **200** |
| Grounding acc., unique 99 | 59 | 72 | 72 | **76** |
| Contradiction acc., all 250 | **245** | 232 | 232 | 232 |
| CONTRADICTORY recall / precision, all | **56/61** / 56/56 | 43/61 / 43/43 | 43/61 / 43/43 | 43/61 / 43/43 |
| Decision FAR, all 250 | **8/168** | 13/168 | 13/168 | 13/168 |
| Decision FAR, unique 99 | 3/61 | **2/61** | **2/61** | **2/61** |
| Decision FRR, all 250 | 50/82 | 27/82 | 27/82 | **27/82** |
| Decision FRR, unique 99 | 22/38 | **11/38** | **11/38** | **11/38** |

Run files: `benchmark/results/v2-m2.{sentence,clause,conjunct}.context.json`.
The ablation over lexical mode and threshold is in ADR-016. With only 68
context groups, most of these differences are within the confidence
intervals (M1 report).

### Error analysis (unique records)

- **False accepts (2 unique, 13 with duplicates):** `synthetic_075` ×7 and
  `synthetic_077` ×6. Both answers are fully supported but incomplete. These
  are the label issues documented in `benchmark/DATASHEET_legacy_v1.md`
  before M2 started. Under the methodology's grounding definition, ACCEPT is
  correct. Completeness is a separate dimension (methodology §3.2).
- **Contradiction misses (7):**
  - 5 are a deliberate change. The legacy labels treat additive facts as
    exclusive ("sells A" vs "sells B", "operates in Rwanda and Tanzania" vs a
    different list), which the methodology classifies as NOT_ENOUGH_INFO
    unless the source claims exhaustiveness (ADR-005).
  - 2 are real gaps: superlatives are exclusive by meaning ("the largest
    ocean": `public_067`), and a year conflict inside a long evidence
    sentence, where the topic gate is diluted (`public_059`). **Not fixed in
    M2**, so the guards are not tuned on seen data. Queued for M4 dev-split
    work.
- **False rejects (11):** all are paraphrase, synonym, or inference
  (bicycles/bikes, people/employees, established/founded, "three offices"
  from a list of three, "early 2021"). This is the expected ceiling of
  deterministic coverage and the motivation for the optional NLI backend.

### Not done / moved

- App factory refactor: moved to M7 (with storage and auth).
- Injection checks on retrieved sources: still M5 (v2 checks the answer only).
- Persistence of v2 evaluations: M7.

**Next (M3):** the declarative policy engine, which must reproduce the
provisional M2 rules exactly, plus HUMAN_REVIEW.

---

## M3 report

**Objective:** replace hard-coded decision rules with versioned, declarative
policies that explain every decision, and add HUMAN_REVIEW.

**Components.** New: `groundguard/policy/` (`model`, `loader`, `engine`,
`facts`, `builtin/*.toml`), `tests/reference/m2_provisional.py` (a frozen
copy of the M2 rule code, used as an oracle). Changed: `pipeline.py` (the
decision now comes from a policy, and the M2 rule table is removed),
`api/v2.py` (`policy` parameter, `GET /v2/policies`), `cli.py`
(`--policy`, `policy list|check`), `bench` (HUMAN_REVIEW metrics, run
schema 2), CI. **Unchanged:** all v0.1.0 modules.

**Equivalence (the condition for removing the M2 code):**
- `provisional-m2` vs the frozen M2 rule code: identical decision, rule id
  and reason on 250 legacy records and 31 probes (281 cases).
- `v1-compat` vs the v0.1.0 decision engine: identical `system_decision` on
  the same 281 cases.
- After the run-schema change, all six existing run files kept identical
  `predictions_hash` values. Only metrics were added.

**Tests.** 427 → 1022 passing (562 of the new tests are per-case
equivalence checks). None weakened or skipped. mypy `--strict` is clean on
all new packages, including `policy`.

### Policies on the probe suite

| Policy | False accepts (of 18) | False rejects (of 13) | HUMAN_REVIEW |
|---|---|---|---|
| provisional-m2 | 0 | 6 | 0 |
| default 2.0.0 | 0 | 6 | 2 (`qual_01_audit`, `qual_03`) |
| strict | 0 | 6 | 0 |

`qual_04` (before/after) is a qualifier mismatch too, but it is rejected
first by the reused v1 relevance check (a "when" question without a year in
the answer). That is the same known limitation recorded in M2.

### Policies on gg-legacy-v1 (seen data)

`default` and `provisional-m2` produce identical decisions: no legacy record
fires the qualifier rule, so the review rate is 0/250. `strict` converts all
FLAGs to REJECT and leaves FAR unchanged (2/61 on unique records). **The
legacy dataset cannot evaluate HUMAN_REVIEW.** Data with scope mismatches is
part of `gg-claims-v2` (M4). Run files:
`benchmark/results/v2-m3.conjunct.{default,strict}.context.json`.

### Design notes

- Policy hashes are computed over parsed canonical content, so comments and
  formatting do not change them, while any change to a rule does.
- `min_confidence_below` is implemented and tested on synthetic facts. It
  cannot fire in production until calibrators exist (M4). This is stated
  in the condition's documentation.
- The API accepts builtin policy names only. Uploading policy files waits for
  authentication (M7). v1-only policies are rejected by the v2 pipeline.

**Next (M4):** `gg-claims-v2` with a frozen held-out split, calibration
(which activates confidence-based review), the optional NLI backend, and
the two contradiction gaps from M2 (superlatives, long-sentence years),
developed on the dev split only.

---

## M4a report (infrastructure; the held-out evaluation is M4b)

**Owner decisions (M4):**
- labels: AI drafts, the owner reviews every record
- annotators: single annotator, agreement not measured
- NLI: build it here, the owner runs it
- domains: health information, and finance & science

**Blocker found.** The environment's network policy denies the public-domain
source hosts (cdc.gov, nih.gov, medlineplus.gov, fda.gov, nasa.gov, usgs.gov,
noaa.gov, bls.gov, sec.gov), and Hugging Face. **No gg-claims-v2 records and
no NLI results exist yet.** Source text is not reconstructed from memory,
because it must be verbatim and traceable.

**Delivered.**

| Area | What | Tests |
|---|---|---|
| Dataset format | `bench/claims_dataset.py`: claim-level records with exact-quote evidence, phenomenon tags, completeness, and an annotation block. The review gate rejects `ai-assistant` as reviewer. `freeze` writes `splits.json` (by context group) only when every record is reviewed. `load_split` detects edits after freezing. The test-access log needs a purpose | 26 |
| Review CLI | `groundguard annotate review/status/freeze`: per-claim keep/change label, exact-quote evidence editing, relevance/completeness, accept / exclude-with-reason / uncertain. Atomic saves, resumable | 8 |
| Claims runner | `groundguard bench claims`: claim-level metrics at oracle segmentation (incl. evidence localization, per phenomenon, per domain) and end-to-end answer metrics. Test runs are logged | 5 |
| Calibration | `calibration/`: isotonic (PAV), Platt, ECE, Brier, reliability bins. Per verifier/label calibration of P(correct). Applied in the pipeline and recorded in the manifest. `groundguard calibrate fit/report`. Refuses test runs | 14 |
| NLI | `verifiers/nli.py`, `[nli]` extra, pinned revisions, model protocol with a deterministic fake for tests, `scripts/run_nli_benchmark.sh` | 8 |

**Found and fixed while building the runner:** guards@1 reported a false
contradiction between sentences that share only their subject (ADR-023).
guards@2 requires shared predicate words. There was no prediction change on
any committed run, and v2 run configs now record the verifier chain.

**Found and recorded, not fixed:** pronoun subjects (`It is not approved
for…`) defeat the single-sentence guards and the two-sentence evidence
window. They are added to the probes (1.1.0) as `coref_01` (goes to
HUMAN_REVIEW, not accepted) and `coref_02` (false reject).

**Tests.** 1022 → 1090 passing. mypy `--strict` is clean on all new
packages. All five v2 run files and the three v0.1.0 run files keep
identical predictions.

### M4b (needs the blocker resolved, then owner review)

1. Draft gg-claims-v2 records from public-domain sources (health, finance
   & science), as `NEEDS_REVIEW`.
2. The owner reviews them (`groundguard annotate review`), then freezes v1.0.
3. On **dev only**: error analysis, the two M2 contradiction gaps
   (superlatives, long-sentence years), the pronoun limitation, and
   calibration fitting.
4. One logged test run per configuration (lexical, and NLI if the owner
   ran it), reported with intervals.

---

## M7a + M5a report (built while M4b is blocked; ADR-026)

**Delivered.**

| Area | What | Tests |
|---|---|---|
| Storage | `storage/v2_store.py`: numbered migrations, hashed API keys, tenant-scoped evaluations with indexed columns, payload modes full/redacted/none, SQL stats, cursor pagination | 8 |
| Service | `create_app(Settings)`. v1 routes moved unchanged into `api/v1.py` (all v1 tests pass unmodified). v2: API-key auth by default, per-key token bucket (429 + Retry-After), body cap (413/411), uniform error envelope | 14 |
| API | persistence of v2 evaluations, `GET /v2/evaluations` (+ `/{id}`), `GET /v2/stats`, `POST /v2/evaluate/batch` (per-item errors, per-item rate cost, auth before body validation) | 8 |
| SDK | `groundguard.sdk.Client`: stdlib, typed errors, retries on 429/5xx/connection errors, tested against the real app in-process and live against uvicorn | 6 |
| CLI | `groundguard keys create/list/revoke` | 1 |
| M5a checks | injection detection on every source; citation markers (masked to keep offsets) verified against cited sources only; default policy 2.1.0 | 8 |
| Docker | installs the package (policies as package data), non-root user, healthcheck, secure env defaults | install simulated in a fresh venv; no Docker daemon available |

**Probes (1.2.0).** `src_inj_01` (poisoned source, supported answer) is no
longer accepted: it goes to HUMAN_REVIEW. `src_inj_02` (text that describes
prompt injection) is a false reject from the answer-level pattern detector,
recorded as a known limitation. False accepts: 0 of 20 must-not-accept
probes.

**Unchanged:** v0.1.0 modules, and every committed run file's predictions.

**Tests.** 1090 → 1139 passing. mypy `--strict` is clean on 49 source files.

**Still blocked:** M4b (needs source access and owner review). The M5
citation and source-injection checks have no quality numbers until a
dataset with citation and injection labels exists.

---

## M6 report (agent traces; built under ADR-026)

**Delivered.** `groundguard/agents/`: trace format and strict parser,
JSON-Schema-subset argument validator, nine deterministic checks, trace
evaluation with the builtin `agent-default` policy, and
`POST /v2/traces/evaluate`. `pipeline.verify_claims` is shared by answer and
trace evaluation. All committed v2 run files still reproduce exactly after
the refactor.

**Trace probes** (`tests/agent_probes/traces.json`, 17, written before the
checks): 16 match their exact expected set of failing checks. No faulty trace
is accepted. Known limitation: `final_contradiction_01`, because guards
compare years, not full dates, so a different day in the same month is FLAG,
not CONTRADICTED.

**Not done (by design).** Planning quality and LLM-judged goal completion,
because they have no deterministic definition (ADR-027). Persistence of trace
evaluations. A benchmark of real agent traces, which needs collected and
reviewed traces.

**Tests.** 1139 → 1179 passing. mypy `--strict` is clean on 54 source files.
