"""Run the v1 (v0.1.0) evaluator over a benchmark dataset.

Input modes make the evaluation input explicit, because it changes results:

``context``
    Production path. Every record goes through
    ``groundguard.application.evaluator.evaluate`` exactly as ``POST /evaluate``
    does: the context is the evidence for every component, and safety checks run.

``oracle``
    Reproduces the v0.1.0 contradiction benchmark test: contradiction receives
    the annotator-selected ``evidence`` (joined) plus the question. Grounding
    and relevance are unchanged. The decision uses the same inputs, without
    safety. Annotator evidence is not available in production, so these
    numbers are an upper bound, not a deployment estimate.

``oracle_no_question``
    Reproduces the v0.1.0 threshold-analysis and decision-metrics tests:
    oracle evidence, question not passed to contradiction.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal, Sequence

from groundguard.application.evaluator import evaluate
from groundguard.bench.datasets import BenchmarkRecord
from groundguard.domain.contradiction import evaluate_contradiction
from groundguard.domain.decision import evaluate_decision
from groundguard.domain.grounding import evaluate_grounding
from groundguard.domain.relevance import evaluate_relevance
from groundguard.evaluation.decision_metrics import reliability_score
from groundguard.pipeline import PipelineConfig, evaluate_v2


InputMode = Literal["context", "oracle", "oracle_no_question"]
INPUT_MODES: tuple[InputMode, ...] = ("context", "oracle", "oracle_no_question")


@dataclass(frozen=True)
class Prediction:
    id: str
    grounding_label: str
    grounding_score: float
    relevance_label: str
    relevance_score: float
    contradiction_label: str
    contradiction_score: float
    reliability_score: float
    system_decision: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _predict_context(record: BenchmarkRecord) -> Prediction:
    result = evaluate(
        question=record.question,
        context=record.context,
        answer=record.answer,
    )
    return Prediction(
        id=record.id,
        grounding_label=result.grounding.label,
        grounding_score=result.decision.grounding_score,
        relevance_label=result.relevance.label,
        relevance_score=result.decision.relevance_score,
        contradiction_label=result.contradiction.label,
        contradiction_score=result.decision.contradiction_score,
        reliability_score=result.decision.reliability_score,
        system_decision=result.decision.system_decision,
    )


def _predict_oracle(record: BenchmarkRecord, *, use_question: bool) -> Prediction:
    grounding = evaluate_grounding(
        record.context,
        record.answer,
        question=record.question,
    )
    relevance = evaluate_relevance(record.question, record.answer)
    contradiction = evaluate_contradiction(
        record.answer,
        " ".join(record.evidence),
        question=record.question if use_question else None,
    )
    decision = evaluate_decision(
        grounding=grounding,
        relevance=relevance,
        contradiction=contradiction,
    )
    return Prediction(
        id=record.id,
        grounding_label=grounding.label,
        grounding_score=decision.grounding_score,
        relevance_label=relevance.label,
        relevance_score=decision.relevance_score,
        contradiction_label=contradiction.label,
        contradiction_score=decision.contradiction_score,
        reliability_score=reliability_score(
            grounding_score=grounding.score,
            relevance_score=relevance.score,
            contradiction_score=contradiction.score,
        ),
        system_decision=decision.system_decision,
    )


def run_v1(
    records: Sequence[BenchmarkRecord],
    input_mode: InputMode,
) -> tuple[Prediction, ...]:
    if input_mode == "context":
        return tuple(_predict_context(record) for record in records)
    if input_mode == "oracle":
        return tuple(_predict_oracle(record, use_question=True) for record in records)
    if input_mode == "oracle_no_question":
        return tuple(_predict_oracle(record, use_question=False) for record in records)
    raise ValueError(f"unknown input_mode {input_mode!r}; expected one of {INPUT_MODES}")


def _predict_v2(record: BenchmarkRecord, config: PipelineConfig) -> Prediction:
    report = evaluate_v2(
        question=record.question,
        context=record.context,
        answer=record.answer,
        config=config,
    )
    labels = [verdict.label for verdict in report.verdicts]
    supported_fraction = labels.count("SUPPORTED") / len(labels) if labels else 0.0
    contradiction_score = 1.0 if "CONTRADICTED" in labels else 0.0
    relevance_score = float(report.relevance["score"])
    decision = report.decision.decision
    if decision not in ("ACCEPT", "FLAG", "REJECT"):
        raise ValueError(f"unexpected decision {decision!r} for a legacy-label benchmark")
    return Prediction(
        id=record.id,
        grounding_label=report.labels["grounding_label"],
        grounding_score=round(supported_fraction, 4),
        relevance_label=str(report.relevance["label"]),
        relevance_score=relevance_score,
        contradiction_label=report.labels["contradiction_label"],
        contradiction_score=contradiction_score,
        reliability_score=round(
            min(supported_fraction, relevance_score, 1.0 - contradiction_score), 4
        ),
        system_decision=decision,
    )


def run_v2(
    records: Sequence[BenchmarkRecord],
    config: PipelineConfig,
) -> tuple[Prediction, ...]:
    """Run the v2 pipeline on the production path (record context as the source).

    Claim verdicts are mapped to the legacy answer-level labels with
    ``pipeline.derive_v1_labels`` so both engines are scored on the same gold labels.
    """

    return tuple(_predict_v2(record, config) for record in records)
