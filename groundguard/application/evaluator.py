from __future__ import annotations

from dataclasses import dataclass

from groundguard.domain.contradiction import (
    ContradictionResult,
    evaluate_contradiction,
)
from groundguard.domain.decision import (
    DecisionResult,
    evaluate_decision,
)
from groundguard.domain.grounding import (
    GroundingResult,
    evaluate_grounding,
)
from groundguard.domain.pii import (
    detect_pii,
)
from groundguard.domain.prompt_injection import (
    PromptInjectionResult,
    detect_prompt_injection,
)
from groundguard.domain.relevance import (
    RelevanceResult,
    evaluate_relevance,
)
from groundguard.domain.safety import (
    PIIDetection,
    PromptInjectionDetection,
    SafetyResult,
    build_safety_result,
)


@dataclass(frozen=True)
class EvaluationResult:
    """
    Complete GroundGuard evaluation result.

    This application-layer object combines the existing
    domain evaluations without introducing new evaluation
    logic.
    """

    grounding: GroundingResult
    relevance: RelevanceResult
    contradiction: ContradictionResult
    pii: PIIDetection
    prompt_injection: PromptInjectionResult
    safety: SafetyResult
    decision: DecisionResult


def _adapt_prompt_injection(
    result: PromptInjectionResult,
) -> PromptInjectionDetection:
    """
    Adapt the prompt-injection detector result to the
    safety domain contract.

    The detector retains its richer category information,
    while SafetyResult currently consumes only detection
    status and evidence.
    """

    return PromptInjectionDetection(
        detected=result.detected,
        evidence=list(
            result.evidence
        ),
    )


def evaluate(
    *,
    question: str,
    context: str,
    answer: str,
    threshold: float | None = None,
) -> EvaluationResult:
    """
    Run the complete GroundGuard evaluation pipeline.

    Pipeline:

        question + context + answer
                    |
                    +--> grounding
                    +--> relevance
                    +--> contradiction
                    +--> PII
                    +--> prompt injection
                              |
                              v
                           safety
                              |
                              v
                           decision

    Contradiction evaluation receives the question so that
    question-aware evaluation can distinguish additive facts
    from genuine conflicts.

    This function only orchestrates existing domain components.
    It does not implement new detection or decision rules.
    """

    grounding = evaluate_grounding(
        context,
        answer,
        question=question,
    )

    relevance = evaluate_relevance(
        question,
        answer,
    )

    contradiction = evaluate_contradiction(
        answer,
        context,
        question=question,
    )

    pii = detect_pii(
        answer,
    )

    prompt_injection = detect_prompt_injection(
        answer,
    )

    safety = build_safety_result(
        pii=pii,
        prompt_injection=_adapt_prompt_injection(
            prompt_injection,
        ),
    )

    decision = evaluate_decision(
        grounding=grounding,
        relevance=relevance,
        contradiction=contradiction,
        safety=safety,
        threshold=threshold,
    )

    return EvaluationResult(
        grounding=grounding,
        relevance=relevance,
        contradiction=contradiction,
        pii=pii,
        prompt_injection=prompt_injection,
        safety=safety,
        decision=decision,
    )