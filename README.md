**GroundGuard — Production-oriented LLM reliability evaluation and hallucination detection system**

GroundGuard is an evaluation layer for LLM applications that evaluates generated answers against supplied source context and produces an auditable ACCEPT / FLAG / REJECT decision. The goal is not to claim universal factual truth, but to measure how reliable an answer is given the evidence and evaluation criteria available to the system. Current release: v0.1.0 — Shipped.

Problem: LLMs can generate answers that sound convincing while being unsupported by the supplied context, irrelevant to the question, contradictory to source information, exposed to personally identifiable information, unsafe, or affected by prompt-injection patterns. GroundGuard separates generation from evaluation by applying measurable reliability and safety checks before an answer is trusted.

*##Core pipeline*:

LLM Answer → GroundGuard Evaluator → Grounding + Relevance + Contradiction + PII + Prompt Injection + Safety → Reliability Score → Decision Engine → ACCEPT / FLAG / REJECT → Structured Evaluation Record → SQLite Persistence → REST API + Dashboard → Docker Deployment.

Grounding evaluates whether substantive claims in the answer are supported by the supplied context. Labels: SUPPORTED, PARTIALLY_SUPPORTED, UNSUPPORTED.

Relevance evaluates whether the answer meaningfully addresses the intended question or task. Labels: RELEVANT, IRRELEVANT.

Contradiction evaluates whether answer claims directly conflict with information supported by the supplied context. Labels: CONTRADICTORY, NOT_CONTRADICTORY. An important design principle is that unsupported does not automatically mean contradictory. For example, if the context says a company was founded in 2018 and the answer says the company has 500 employees, the employee count is unsupported but not contradicted by the context. If the answer instead says the company was founded in 2015, it directly contradicts the evidence.

The safety layer evaluates PII detection, prompt-injection patterns, and safety status. PII evaluation exposes whether sensitive information was detected and its categories. Prompt-injection evaluation identifies potential injection patterns. Safety evaluation exposes safety status and evidence.

The decision engine combines evaluation signals into a reliability score and compares the result against a configurable threshold. The system exposes component scores, component labels, reliability score, threshold, final label, system decision, and decision reason. Decisions are ACCEPT, FLAG, or REJECT.

*Example evaluation*:

Grounding: 1.00 — SUPPORTED
Relevance: 1.00 — RELEVANT
Contradiction: 0.00 — NOT_CONTRADICTORY
Reliability: 1.00
Threshold: 0.70
Decision: ACCEPT
Label: RELIABLE

*Architecture:*

groundguard/
├── api/
│   ├── app.py
│   ├── dashboard.py
│   └── schemas.py
├── application/
│   └── evaluator.py
├── domain/
│   ├── claims.py
│   ├── contradiction.py
│   ├── decision.py
│   ├── grounding.py
│   ├── pii.py
│   ├── prompt_injection.py
│   ├── propositions.py
│   ├── proposition_comparison.py
│   ├── relevance.py
│   └── safety.py
├── evaluation/
│   ├── decision_metrics.py
│   ├── evaluation_record.py
│   └── thresholds.py
└── storage/
    ├── evaluation_store.py
    └── __init__.py

The domain layer contains core evaluation and decision logic. The application layer coordinates the evaluation pipeline. The evaluation layer defines evaluation records, metrics, and thresholds. The storage layer provides SQLite-backed persistence. The API layer exposes the system through FastAPI and provides the dashboard. This separation keeps evaluation logic independent from transport and persistence.

Every evaluation becomes a structured, auditable record containing the question, context, answer, final label, reliability status, system decision, grounding score, relevance score, contradiction score, reliability score, threshold, component labels, PII results, prompt-injection results, safety results, decision reason, evaluation ID, and creation timestamp.

GroundGuard uses SQLite for persistent evaluation storage. The storage layer supports saving evaluations, retrieving evaluations, retrieving by ID, pagination, decision filtering, counting, and clearing records. Docker stores the production database at /app/data/groundguard.db using a named Docker volume so evaluation history survives container replacement. The production database path is configurable through GROUNDGUARD_DATABASE_PATH=/app/data/groundguard.db.

*REST API:*

GET  /health
POST /evaluate
GET  /evaluations
GET  /evaluations/{evaluation_id}
GET  /evaluations/stats
GET  /dashboard

GET /health verifies service availability.

POST /evaluate accepts a question, context, answer, and optional reliability threshold and returns the evaluation ID, decision, scores, labels, safety signals, and reason.

GET /evaluations returns persisted evaluation history with pagination and decision filtering.

GET /evaluations/{evaluation_id} retrieves a specific evaluation record.

GET /evaluations/stats returns total evaluations, ACCEPT / FLAG / REJECT counts, decision rates, average reliability, and safety violations.

GET /dashboard provides a human-readable interface for inspecting evaluation activity and results.

Benchmark methodology focuses on grounding, relevance, and contradiction. The V1 benchmark target is 250 human-labeled examples covering fully supported answers, partially supported answers, unsupported answers, contradictory answers, relevant but unsupported answers, irrelevant answers, multi-claim and edge cases, numerical claims, temporal claims, and paraphrases. The benchmark methodology and annotation rules are documented in docs/evaluation_specification.md, docs/annotation_guidelines.md, and docs/public_text_sourcing_policy.md.

*Target benchmark distribution:*

Fully supported: 50
Partially supported: 35
Unsupported: 35
Contradictory: 35
Relevant but unsupported: 25
Irrelevant: 25
Multi-claim / edge cases: 25
Numerical / temporal / paraphrase: 20
Total: 250

These targets describe benchmark construction rather than expected real-world class frequencies.

Testing is a major part of the project. The automated suite covers API behavior, evaluation pipeline, grounding, grounding regressions, relevance, relevance regressions, contradiction, contradiction regressions, structured contradiction evaluation, proposition analysis, PII detection, prompt injection, safety, decision logic, decision metrics, thresholds, threshold integration, evaluation records, persistent storage, pagination, filtering, benchmark schemas, benchmark records, benchmark manifests, dashboard behavior, and production behavior.

Current release validation: 226 tests passed.

Run the complete test suite with:

pytest

*Docker deployment*

docker build -t groundguard:0.1.0 .

docker volume create groundguard-data

docker run -d `
    --name groundguard `
    -p 8002:8000 `
    -v groundguard-data:/app/data `
    groundguard:0.1.0

Verify:

Invoke-RestMethod http://localhost:8002/health

Expected:

status
------
ok

The deployed system was validated through the health endpoint, evaluation endpoint, evaluation history endpoint, statistics endpoint, SQLite persistence, and container replacement persistence.

*Production validation for v0.1.0:*

226 automated tests passed
Docker image successfully built
Container successfully started
/health verified
/evaluate verified
/evaluations verified
/evaluations/stats verified
SQLite persistence verified
Container replacement persistence verified

*Engineering principles:*

Evidence over assumptions — evaluation is performed against supplied context rather than silently relying on external knowledge.

Unsupported does not mean contradictory — lack of evidence and conflicting evidence are treated as different failure modes.

Explicit decisions — scores, labels, thresholds, and reasons are exposed rather than returning an opaque reliability result.

Separation of concerns — evaluation, orchestration, API, and persistence are independently structured.

Auditability — evaluations are persisted as structured records with IDs and timestamps.

Focused engineering — v0.1.0 prioritizes a complete, tested, deployable system instead of unnecessary infrastructure or feature accumulation.

Limitations: GroundGuard evaluates answers relative to the supplied context and configured evaluation methodology. It does not guarantee universal factual truth. Evaluation quality depends on the supplied context, unsupported claims may require external verification, benchmark targets do not represent real-world class frequencies, SQLite is intended for the current release rather than high-scale workloads, and reliability thresholds require calibration for the target application.

Future work should be driven by measured failures and deployment requirements rather than feature accumulation. Potential directions include broader benchmark coverage, improved evaluator accuracy, richer failure analysis, latency and cost measurement, production-scale persistence, and additional evaluator strategies. These are future directions and are not requirements of v0.1.0.

*GroundGuard v0.1.0 demonstrates an end-to-end LLM reliability evaluation workflow:*

LLM Answer
↓
Evaluation
↓
Reliability Decision
↓
Structured Evaluation Record
↓
Persistent Storage
↓
Statistics / Observability
↓
REST API + Dashboard
↓
Docker Deployment

Status: Shipped.
Release: v0.1.0.