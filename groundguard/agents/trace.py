"""Agent execution traces: a self-contained JSON format and strict parsing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from groundguard.core.errors import InvalidInput


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]
    result: str | None
    error: str | None

    @property
    def succeeded(self) -> bool:
        return self.error is None


@dataclass(frozen=True)
class Step:
    index: int
    kind: Literal["llm", "tool_call", "retrieval"]
    text: str | None = None
    call: ToolCall | None = None


@dataclass(frozen=True)
class Trace:
    id: str
    goal: str
    tools: tuple[ToolSpec, ...]
    steps: tuple[Step, ...]
    final_answer: str
    forbidden_tools: tuple[str, ...] = ()
    max_tool_calls: int | None = None
    expected_tools: tuple[str, ...] | None = None

    @property
    def calls(self) -> tuple[ToolCall, ...]:
        return tuple(step.call for step in self.steps if step.call is not None)


def _string(value: Any, where: str, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str) or (not optional and not value.strip()):
        raise InvalidInput(f"{where}: must be a non-empty string")
    return value


def parse_trace(data: Any) -> Trace:
    if not isinstance(data, dict):
        raise InvalidInput("trace must be an object")
    allowed = {"id", "goal", "tools", "policy", "steps", "final_answer", "expected_tools"}
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise InvalidInput(f"trace: unknown keys {unknown}")
    for key in ("id", "goal", "tools", "steps", "final_answer"):
        if key not in data:
            raise InvalidInput(f"trace: missing {key!r}")

    tools: list[ToolSpec] = []
    for index, raw in enumerate(data["tools"]):
        where = f"tools[{index}]"
        if not isinstance(raw, dict):
            raise InvalidInput(f"{where}: must be an object")
        parameters = raw.get("parameters", {"type": "object"})
        if not isinstance(parameters, dict):
            raise InvalidInput(f"{where}.parameters: must be a JSON-Schema object")
        tools.append(ToolSpec(str(_string(raw.get("name"), f"{where}.name")), str(raw.get("description", "")), parameters))
    if len({tool.name for tool in tools}) != len(tools):
        raise InvalidInput("tools: duplicate tool names")

    policy = data.get("policy") or {}
    if not isinstance(policy, dict) or set(policy) - {"forbidden_tools", "max_tool_calls"}:
        raise InvalidInput("policy: only 'forbidden_tools' and 'max_tool_calls' are supported")
    max_calls = policy.get("max_tool_calls")
    if max_calls is not None and (not isinstance(max_calls, int) or isinstance(max_calls, bool) or max_calls < 1):
        raise InvalidInput("policy.max_tool_calls: must be a positive integer")

    steps: list[Step] = []
    if not isinstance(data["steps"], list):
        raise InvalidInput("steps: must be a list")
    for index, raw in enumerate(data["steps"]):
        where = f"steps[{index}]"
        if not isinstance(raw, dict) or raw.get("kind") not in ("llm", "tool_call", "retrieval"):
            raise InvalidInput(f"{where}: kind must be 'llm', 'tool_call' or 'retrieval'")
        if raw["kind"] == "tool_call":
            arguments = raw.get("arguments", {})
            if not isinstance(arguments, dict):
                raise InvalidInput(f"{where}.arguments: must be an object")
            result = _string(raw.get("result"), f"{where}.result", optional=True)
            error = _string(raw.get("error"), f"{where}.error", optional=True)
            if (result is None) == (error is None):
                raise InvalidInput(f"{where}: a tool call has exactly one of 'result' or 'error'")
            call = ToolCall(
                id=str(_string(raw.get("id", f"call-{index}"), f"{where}.id")),
                name=str(_string(raw.get("name"), f"{where}.name")),
                arguments=arguments,
                result=result,
                error=error,
            )
            steps.append(Step(index, "tool_call", call=call))
        else:
            steps.append(Step(index, raw["kind"], text=_string(raw.get("text"), f"{where}.text")))

    expected = data.get("expected_tools")
    if expected is not None and (not isinstance(expected, list) or not all(isinstance(x, str) for x in expected)):
        raise InvalidInput("expected_tools: must be a list of tool names")

    return Trace(
        id=str(_string(data["id"], "id")),
        goal=str(_string(data["goal"], "goal")),
        tools=tuple(tools),
        steps=tuple(steps),
        final_answer=str(_string(data["final_answer"], "final_answer")),
        forbidden_tools=tuple(policy.get("forbidden_tools", []) or []),
        max_tool_calls=max_calls,
        expected_tools=None if expected is None else tuple(expected),
    )
