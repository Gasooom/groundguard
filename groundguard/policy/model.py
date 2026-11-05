"""Policy model: ordered rules over a closed vocabulary of conditions.

A rule's ``when`` table may hold several conditions; all must hold (AND).
There is no expression language and nothing is evaluated as code (ADR-008).

Condition vocabulary
--------------------
check_failed = "pii" | "prompt_injection" | "relevance" | "source_injection" | "citation"
any_claim = LABEL                      at least one claim has LABEL
no_claim = LABEL                       no claim has LABEL (true when there are no claims)
claim_fraction_above = {label, value}  share of claims with LABEL is > value (false with no claims)
any_signal = "negation" | "quantity" | "date" | "qualifier"
min_confidence_below = VALUE           some claim has a confidence below VALUE; claims
                                       without a calibrated confidence are ignored, so this
                                       never fires for uncalibrated verifiers
"v1.unsafe" = true                     v1-compatible policies only
"v1.grounding" / "v1.relevance" / "v1.contradiction" = V1 LABEL
"v1.reliability_below_threshold" = true
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from groundguard.core.types import VERDICT_LABELS, DecisionLabel, VerdictLabel
from groundguard.policy.facts import CHECK_NAMES, EvaluationFacts


DECISIONS: tuple[DecisionLabel, ...] = ("ACCEPT", "FLAG", "REJECT", "HUMAN_REVIEW")
SIGNALS = ("negation", "quantity", "date", "qualifier")
V1_LABELS: dict[str, tuple[str, ...]] = {
    "v1.grounding": ("SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED"),
    "v1.relevance": ("RELEVANT", "IRRELEVANT"),
    "v1.contradiction": ("CONTRADICTORY", "NOT_CONTRADICTORY"),
}
V1_FLAGS = ("v1.unsafe", "v1.reliability_below_threshold")

ConditionKind = Literal[
    "check_failed",
    "any_claim",
    "no_claim",
    "claim_fraction_above",
    "any_signal",
    "min_confidence_below",
    "v1.unsafe",
    "v1.grounding",
    "v1.relevance",
    "v1.contradiction",
    "v1.reliability_below_threshold",
]
CONDITION_KINDS: tuple[str, ...] = (
    "check_failed",
    "any_claim",
    "no_claim",
    "claim_fraction_above",
    "any_signal",
    "min_confidence_below",
    *V1_FLAGS,
    *V1_LABELS,
)


class PolicyError(ValueError):
    """A policy file is malformed or uses an unknown condition or decision."""


@dataclass(frozen=True)
class Condition:
    kind: str
    value: Any

    def holds(self, facts: EvaluationFacts) -> bool:
        claims = facts.claims
        if self.kind == "check_failed":
            return bool(self.value in facts.failed_checks)
        if self.kind == "any_claim":
            return any(claim.label == self.value for claim in claims)
        if self.kind == "no_claim":
            return all(claim.label != self.value for claim in claims)
        if self.kind == "claim_fraction_above":
            if not claims:
                return False
            share = sum(claim.label == self.value["label"] for claim in claims) / len(claims)
            return bool(share > self.value["value"])
        if self.kind == "any_signal":
            return any(self.value in claim.signals for claim in claims)
        if self.kind == "min_confidence_below":
            confidences = [claim.confidence for claim in claims if claim.confidence is not None]
            return bool(confidences) and min(confidences) < self.value
        if self.kind.startswith("v1."):
            if facts.v1 is None:
                raise PolicyError(f"condition {self.kind!r} needs v1 facts; use it with the v1 engine")
            attribute = getattr(facts.v1, self.kind.removeprefix("v1."))
            return bool(attribute == self.value)
        raise PolicyError(f"unknown condition {self.kind!r}")  # guarded by the loader

    def to_dict(self) -> dict[str, Any]:
        return {self.kind: self.value}


def validate_condition(kind: str, value: Any, where: str) -> Condition:
    def fail(message: str) -> PolicyError:
        return PolicyError(f"{where}.{kind}: {message}")

    if kind not in CONDITION_KINDS:
        raise PolicyError(f"{where}: unknown condition {kind!r}; known: {list(CONDITION_KINDS)}")
    if kind == "check_failed":
        if value not in CHECK_NAMES:
            raise fail(f"must be one of {list(CHECK_NAMES)}")
    elif kind in ("any_claim", "no_claim"):
        if value not in VERDICT_LABELS:
            raise fail(f"must be one of {list(VERDICT_LABELS)}")
    elif kind == "claim_fraction_above":
        if not isinstance(value, dict) or set(value) != {"label", "value"}:
            raise fail("must be a table with exactly 'label' and 'value'")
        if value["label"] not in VERDICT_LABELS:
            raise fail(f"label must be one of {list(VERDICT_LABELS)}")
        if not _is_unit_interval(value["value"]):
            raise fail("value must be a number in [0, 1]")
        value = {"label": value["label"], "value": float(value["value"])}
    elif kind == "any_signal":
        if value not in SIGNALS:
            raise fail(f"must be one of {list(SIGNALS)}")
    elif kind == "min_confidence_below":
        if not _is_unit_interval(value):
            raise fail("must be a number in [0, 1]")
        value = float(value)
    elif kind in V1_FLAGS:
        if value is not True:
            raise fail("must be true")
    elif kind in V1_LABELS:
        if value not in V1_LABELS[kind]:
            raise fail(f"must be one of {list(V1_LABELS[kind])}")
    return Condition(kind, value)


def _is_unit_interval(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and 0.0 <= value <= 1.0


@dataclass(frozen=True)
class Rule:
    id: str
    when: tuple[Condition, ...]
    decision: DecisionLabel
    description: str
    terminal: bool = True

    def holds(self, facts: EvaluationFacts) -> bool:
        return all(condition.holds(facts) for condition in self.when)

    def to_dict(self) -> dict[str, Any]:
        when: dict[str, Any] = {}
        for condition in self.when:
            when.update(condition.to_dict())
        return {
            "id": self.id,
            "when": when,
            "decision": self.decision,
            "description": self.description,
            "terminal": self.terminal,
        }


@dataclass(frozen=True)
class Policy:
    id: str
    version: str
    description: str
    rules: tuple[Rule, ...]
    default_decision: DecisionLabel
    default_description: str
    default_rule_id: str = "default"
    hash: str = field(default="", compare=False)

    @property
    def requires_v1(self) -> bool:
        """True if any rule uses v1.* conditions (usable with the v1 engine only)."""

        return any(condition.kind.startswith("v1.") for rule in self.rules for condition in rule.when)

    def to_dict(self) -> dict[str, Any]:
        """Canonical content. The policy hash is computed over this, so
        comments and formatting in the TOML file do not change it."""

        return {
            "id": self.id,
            "version": self.version,
            "description": self.description,
            "rules": [rule.to_dict() for rule in self.rules],
            "default": {
                "id": self.default_rule_id,
                "decision": self.default_decision,
                "description": self.default_description,
            },
        }


__all__ = [
    "Condition",
    "DECISIONS",
    "Policy",
    "PolicyError",
    "Rule",
    "SIGNALS",
    "VerdictLabel",
    "validate_condition",
]
