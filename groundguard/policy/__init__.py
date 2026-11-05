"""Declarative decision policies (ADR-008)."""

from groundguard.policy.engine import PolicyDecision, decide
from groundguard.policy.facts import EvaluationFacts, facts_from_v1, facts_from_v2
from groundguard.policy.loader import builtin_names, load_builtin, load_policy, load_policy_text
from groundguard.policy.model import Policy, PolicyError

DEFAULT_POLICY = "default"

__all__ = [
    "DEFAULT_POLICY",
    "EvaluationFacts",
    "Policy",
    "PolicyDecision",
    "PolicyError",
    "builtin_names",
    "decide",
    "facts_from_v1",
    "facts_from_v2",
    "load_builtin",
    "load_policy",
    "load_policy_text",
]
