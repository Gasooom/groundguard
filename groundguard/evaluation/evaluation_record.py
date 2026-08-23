from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from groundguard.application.evaluator import EvaluationResult


@dataclass(frozen=True)
class EvaluationRecord:
    """
    Serializable record of one GroundGuard evaluation.

    This object captures the final evaluation state without
    introducing any new evaluation logic.
    """

    question: str
    context: str
    answer: str

    label: str
    reliable: bool
    system_decision: str

    grounding_score: float
    relevance_score: float
    contradiction_score: float
    reliability_score: float
    threshold: float

    grounding_label: str
    relevance_label: str
    contradiction_label: str

    pii_detected: bool
    pii_categories: list[str]

    prompt_injection_detected: bool

    safety_safe: bool
    safety_evidence: list[str]

    reason: str

    @classmethod
    def from_evaluation(
        cls,
        *,
        question: str,
        context: str,
        answer: str,
        result: "EvaluationResult",
    ) -> "EvaluationRecord":
        """
        Build a serializable record from an evaluation result.
        """

        return cls(
            question=question,
            context=context,
            answer=answer,
            label=result.decision.label,
            reliable=result.decision.reliable,
            system_decision=result.decision.system_decision,
            grounding_score=result.decision.grounding_score,
            relevance_score=result.decision.relevance_score,
            contradiction_score=result.decision.contradiction_score,
            reliability_score=result.decision.reliability_score,
            threshold=result.decision.threshold,
            grounding_label=result.grounding.label,
            relevance_label=result.relevance.label,
            contradiction_label=result.contradiction.label,
            pii_detected=result.pii.detected,
            pii_categories=list(result.pii.categories),
            prompt_injection_detected=result.prompt_injection.detected,
            safety_safe=result.safety.safe,
            safety_evidence=list(result.safety.evidence),
            reason=result.decision.reason,
        )

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the evaluation record into JSON-compatible data.
        """

        return asdict(self)