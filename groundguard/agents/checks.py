"""Deterministic checks over an agent execution trace.

Each check returns ``{"name", "status", "findings"}`` with status PASS,
WARN, FAIL or NOT_APPLICABLE. A finding names the step it concerns.

tool_allowlist          every call uses a provided tool that the deployment does not forbid
argument_validity       arguments validate against the tool's JSON-Schema subset
redundant_calls         a successful call identical to the immediately preceding call
call_budget             number of tool calls within policy.max_tool_calls
error_handling          after a failed call the agent either recovers with a later
                        successful call, or the final answer acknowledges the failure
tool_output_injection   instruction-like text inside a tool output
state_consistency       intermediate LLM steps do not contradict earlier tool results
final_answer_grounding  final-answer claims verified against tool outputs and
                        retrieval steps (CONTRADICTED -> FAIL, NOT_ENOUGH_INFO -> WARN)
tool_selection          every expected tool was called (only if expected_tools is given)
"""

from __future__ import annotations

import json
import re
from typing import Any, Literal, Sequence

from groundguard.agents.schema_validate import validate
from groundguard.agents.trace import Trace
from groundguard.core.types import ClaimVerdict, SourceDocument
from groundguard.domain.prompt_injection import detect_prompt_injection
from groundguard.pipeline import PipelineConfig, verify_claims


Status = Literal["PASS", "WARN", "FAIL", "NOT_APPLICABLE"]
TRACE_CHECKS = (
    "tool_allowlist",
    "argument_validity",
    "redundant_calls",
    "call_budget",
    "error_handling",
    "tool_output_injection",
    "state_consistency",
    "final_answer_grounding",
    "tool_selection",
)

_ACKNOWLEDGES_FAILURE = re.compile(
    r"\b(?:could not|couldn't|cannot|can't|unable|failed|unavailable|not available|error|was not able)\b",
    re.IGNORECASE,
)


def _result(name: str, findings: list[dict[str, Any]], *, fail: bool, warn: bool = False,
            applicable: bool = True) -> dict[str, Any]:
    status: Status = "NOT_APPLICABLE" if not applicable else "FAIL" if fail else "WARN" if warn else "PASS"
    return {"name": name, "status": status, "findings": findings}


def _canonical(arguments: dict[str, Any]) -> str:
    return json.dumps(arguments, sort_keys=True, separators=(",", ":"))


def tool_allowlist(trace: Trace) -> dict[str, Any]:
    known = {tool.name for tool in trace.tools}
    findings = []
    for step in trace.steps:
        if step.call is None:
            continue
        if step.call.name not in known:
            findings.append({"step": step.index, "message": f"unknown tool {step.call.name!r}"})
        elif step.call.name in trace.forbidden_tools:
            findings.append({"step": step.index, "message": f"forbidden tool {step.call.name!r}"})
    return _result("tool_allowlist", findings, fail=bool(findings))


def argument_validity(trace: Trace) -> dict[str, Any]:
    specs = {tool.name: tool for tool in trace.tools}
    findings = []
    for step in trace.steps:
        if step.call is None or step.call.name not in specs:
            continue  # unknown tools are reported by tool_allowlist
        for error in validate(step.call.arguments, specs[step.call.name].parameters):
            findings.append({"step": step.index, "tool": step.call.name, "message": error})
    return _result("argument_validity", findings, fail=bool(findings))


def redundant_calls(trace: Trace) -> dict[str, Any]:
    findings = []
    previous = None
    for step in trace.steps:
        if step.call is None:
            continue
        key = (step.call.name, _canonical(step.call.arguments))
        if previous is not None and previous[0] == key and previous[1].succeeded and step.call.succeeded:
            findings.append({"step": step.index, "message": f"repeats the previous successful {step.call.name!r} call"})
        previous = (key, step.call)
    return _result("redundant_calls", findings, fail=bool(findings))


def call_budget(trace: Trace) -> dict[str, Any]:
    if trace.max_tool_calls is None:
        return _result("call_budget", [], fail=False, applicable=False)
    count = len(trace.calls)
    findings = [] if count <= trace.max_tool_calls else [
        {"message": f"{count} tool calls exceed the budget of {trace.max_tool_calls}"}
    ]
    return _result("call_budget", findings, fail=bool(findings))


def error_handling(trace: Trace) -> dict[str, Any]:
    findings = []
    failed_any = False
    for position, step in enumerate(trace.steps):
        if step.call is None or step.call.succeeded:
            continue
        failed_any = True
        later_success = any(
            later.call is not None and later.call.succeeded
            and (later.call.name != step.call.name or _canonical(later.call.arguments) != _canonical(step.call.arguments))
            for later in trace.steps[position + 1 :]
        )
        acknowledged = bool(_ACKNOWLEDGES_FAILURE.search(trace.final_answer))
        if not later_success and not acknowledged:
            findings.append({
                "step": step.index,
                "message": f"{step.call.name!r} failed ({step.call.error}); no later call recovered "
                           "and the final answer does not acknowledge the failure",
            })
    return _result("error_handling", findings, fail=bool(findings), applicable=failed_any)


def _tool_sources(trace: Trace, *, before: int | None = None) -> list[SourceDocument]:
    sources = []
    for step in trace.steps:
        if before is not None and step.index >= before:
            break
        if step.call is not None and step.call.succeeded and step.call.result:
            sources.append(SourceDocument(f"step-{step.index}:{step.call.name}", step.call.result, kind="tool_output"))
        elif step.kind == "retrieval" and step.text:
            sources.append(SourceDocument(f"step-{step.index}:retrieval", step.text, kind="tool_output"))
    return sources


def tool_output_injection(trace: Trace) -> dict[str, Any]:
    findings = []
    for source in _tool_sources(trace):
        result = detect_prompt_injection(source.text)
        if result.detected:
            findings.append({"source_id": source.id, "categories": list(result.categories),
                             "evidence": list(result.evidence)})
    return _result("tool_output_injection", findings, fail=bool(findings))


def state_consistency(trace: Trace, config: PipelineConfig) -> dict[str, Any]:
    findings = []
    checked = False
    for step in trace.steps:
        if step.kind != "llm" or not step.text:
            continue
        sources = _tool_sources(trace, before=step.index)
        if not sources:
            continue
        checked = True
        claims, verdicts = verify_claims(step.text, sources, config)
        text_by_id = {claim.id: claim.text for claim in claims}
        for verdict in verdicts:
            if verdict.label == "CONTRADICTED":
                findings.append({
                    "step": step.index,
                    "claim": text_by_id[verdict.claim_id],
                    "evidence": [item.text for item in verdict.evidence],
                    "message": "an intermediate step contradicts an earlier tool result",
                })
    return _result("state_consistency", findings, fail=bool(findings), applicable=checked)


def final_answer_grounding(trace: Trace, config: PipelineConfig) -> tuple[dict[str, Any], tuple[ClaimVerdict, ...], Any]:
    sources = _tool_sources(trace)
    claims, verdicts = verify_claims(trace.final_answer, sources, config)
    labels = [verdict.label for verdict in verdicts]
    text_by_id = {claim.id: claim.text for claim in claims}
    findings = [
        {"claim": text_by_id[v.claim_id], "label": v.label, "evidence": [e.text for e in v.evidence],
         "verifier": v.verifier}
        for v in verdicts if v.label != "SUPPORTED"
    ]
    result = _result(
        "final_answer_grounding", findings,
        fail="CONTRADICTED" in labels, warn="NOT_ENOUGH_INFO" in labels,
    )
    return result, verdicts, claims


def tool_selection(trace: Trace) -> dict[str, Any]:
    if trace.expected_tools is None:
        return _result("tool_selection", [], fail=False, applicable=False)
    called = [call.name for call in trace.calls]
    missing = [name for name in trace.expected_tools if name not in called]
    iterator = iter(called)
    subsequence = all(name in iterator for name in trace.expected_tools)
    result = _result(
        "tool_selection",
        [{"message": f"expected tool {name!r} was not called"} for name in missing],
        fail=bool(missing),
    )
    result["match"] = {
        "exact_sequence": called == list(trace.expected_tools),
        "subsequence": subsequence,
        "set": set(trace.expected_tools) <= set(called),
    }
    return result


def run_checks(trace: Trace, config: PipelineConfig) -> tuple[list[dict[str, Any]], Sequence[ClaimVerdict], Any]:
    grounding, verdicts, claims = final_answer_grounding(trace, config)
    checks = [
        tool_allowlist(trace),
        argument_validity(trace),
        redundant_calls(trace),
        call_budget(trace),
        error_handling(trace),
        tool_output_injection(trace),
        state_consistency(trace, config),
        grounding,
        tool_selection(trace),
    ]
    return checks, verdicts, claims
