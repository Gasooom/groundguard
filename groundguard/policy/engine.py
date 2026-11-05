"""Evaluate a policy over evaluation facts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from groundguard.core.types import DecisionLabel
from groundguard.policy.facts import EvaluationFacts
from groundguard.policy.model import Policy


@dataclass(frozen=True)
class PolicyDecision:
    decision: DecisionLabel
    rule: str
    reason: str
    policy_id: str
    policy_version: str
    policy_hash: str
    matched_rules: tuple[str, ...]   # every rule whose conditions held, in order
    annotations: tuple[str, ...]     # matched non-terminal rules

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "rule": self.rule,
            "reason": self.reason,
            "policy": {"id": self.policy_id, "version": self.policy_version, "hash": self.policy_hash},
            "matched_rules": list(self.matched_rules),
            "annotations": list(self.annotations),
        }


def decide(policy: Policy, facts: EvaluationFacts) -> PolicyDecision:
    """Rules are checked in order; the first terminal rule that holds decides.

    Every rule is checked, even after the decision is made, so
    ``matched_rules`` shows all the reasons an answer could have been
    flagged, not only the one that won.
    """

    matched: list[str] = []
    annotations: list[str] = []
    deciding = None
    for rule in policy.rules:
        if not rule.holds(facts):
            continue
        matched.append(rule.id)
        if not rule.terminal:
            annotations.append(rule.id)
        elif deciding is None:
            deciding = rule

    if deciding is None:
        decision, rule_id, reason = policy.default_decision, policy.default_rule_id, policy.default_description
    else:
        decision, rule_id, reason = deciding.decision, deciding.id, deciding.description

    return PolicyDecision(
        decision=decision,
        rule=rule_id,
        reason=reason,
        policy_id=policy.id,
        policy_version=policy.version,
        policy_hash=policy.hash,
        matched_rules=tuple(matched),
        annotations=tuple(annotations),
    )
