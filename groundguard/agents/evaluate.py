"""Evaluate an agent trace: deterministic checks, then a trace policy."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from groundguard.agents.checks import run_checks
from groundguard.agents.trace import Trace, parse_trace
from groundguard.core.serialization import sha256_json
from groundguard.pipeline import ENGINE_VERSION, PipelineConfig
from groundguard.policy import Policy, decide, facts_from_v2, load_builtin


DEFAULT_TRACE_POLICY = "agent-default"


def evaluate_trace(
    trace: Trace | dict[str, Any],
    *,
    policy: Policy | None = None,
    config: PipelineConfig | None = None,
) -> dict[str, Any]:
    parsed = trace if isinstance(trace, Trace) else parse_trace(trace)
    config = config or PipelineConfig()
    policy = policy or load_builtin(DEFAULT_TRACE_POLICY)

    checks, verdicts, claims = run_checks(parsed, config)
    failed = frozenset(check["name"] for check in checks if check["status"] == "FAIL")
    facts = facts_from_v2(verdicts, relevant=True, pii_detected=False, injection_detected=False)
    decision = decide(policy, replace(facts, failed_trace_checks=failed))

    return {
        "trace_id": parsed.id,
        "checks": checks,
        "failed_checks": sorted(failed),
        "final_answer": {
            "claims": [claim.to_dict() for claim in claims],
            "verdicts": [verdict.to_dict() for verdict in verdicts],
        },
        "decision": decision.to_dict(),
        "manifest": {
            "engine": "v2-trace",
            "engine_version": ENGINE_VERSION,
            "verifier_chain": list(config.chain().ids),
            "policy": {"id": policy.id, "version": policy.version, "hash": policy.hash},
            "config_hash": sha256_json({"engine_version": ENGINE_VERSION, **config.to_dict(),
                                        "policy_hash": policy.hash}),
        },
    }
