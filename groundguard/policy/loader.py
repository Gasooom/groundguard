"""Load and strictly validate TOML policies (stdlib ``tomllib``).

File layout::

    [policy]
    id = "default"
    version = "2.0.0"
    description = "..."

    [[rule]]
    id = "grounding.contradicted"
    when = { any_claim = "CONTRADICTED" }
    decision = "REJECT"
    description = "At least one claim is contradicted by the evidence."
    # terminal = true   (default; non-terminal rules only annotate)

    [default]
    id = "default.accept"
    decision = "ACCEPT"
    description = "..."
"""

from __future__ import annotations

import tomllib
from dataclasses import replace
from importlib import resources
from pathlib import Path
from typing import Any

from groundguard.core.serialization import sha256_json
from groundguard.policy.model import DECISIONS, Policy, PolicyError, Rule, validate_condition


BUILTIN_PACKAGE = "groundguard.policy.builtin"

_TOP_LEVEL = {"policy", "rule", "default"}
_POLICY_KEYS = {"id", "version", "description"}
_RULE_KEYS = {"id", "when", "decision", "description", "terminal"}
_DEFAULT_KEYS = {"id", "decision", "description"}


def _require_keys(table: Any, required: set[str], allowed: set[str], where: str) -> dict[str, Any]:
    if not isinstance(table, dict):
        raise PolicyError(f"{where}: expected a table")
    unknown = sorted(set(table) - allowed)
    if unknown:
        raise PolicyError(f"{where}: unknown keys {unknown}")
    missing = sorted(required - set(table))
    if missing:
        raise PolicyError(f"{where}: missing keys {missing}")
    for key in required & {"id", "version", "description", "decision"}:
        if not isinstance(table[key], str) or not table[key].strip():
            raise PolicyError(f"{where}.{key}: must be a non-empty string")
    return table


def _decision(value: str, where: str) -> Any:
    if value not in DECISIONS:
        raise PolicyError(f"{where}.decision: {value!r} is not one of {list(DECISIONS)}")
    return value


def parse_policy(data: dict[str, Any]) -> Policy:
    unknown = sorted(set(data) - _TOP_LEVEL)
    if unknown:
        raise PolicyError(f"unknown top-level tables {unknown}")
    if "policy" not in data or "default" not in data:
        raise PolicyError("a policy needs [policy] and [default] tables")

    header = _require_keys(data["policy"], _POLICY_KEYS, _POLICY_KEYS, "policy")
    default = _require_keys(data["default"], _DEFAULT_KEYS, _DEFAULT_KEYS, "default")

    raw_rules = data.get("rule", [])
    if not isinstance(raw_rules, list):
        raise PolicyError("rule: use [[rule]] array-of-tables")

    rules: list[Rule] = []
    seen = {default["id"]}
    for index, raw in enumerate(raw_rules):
        where = f"rule[{index}]"
        table = _require_keys(raw, _RULE_KEYS - {"terminal"}, _RULE_KEYS, where)
        if table["id"] in seen:
            raise PolicyError(f"{where}.id: duplicate rule id {table['id']!r}")
        seen.add(table["id"])
        when = table["when"]
        if not isinstance(when, dict) or not when:
            raise PolicyError(f"{where}.when: must be a non-empty table of conditions")
        terminal = table.get("terminal", True)
        if not isinstance(terminal, bool):
            raise PolicyError(f"{where}.terminal: must be true or false")
        rules.append(
            Rule(
                id=table["id"],
                when=tuple(
                    validate_condition(kind, value, f"{where}.when")
                    for kind, value in sorted(when.items())
                ),
                decision=_decision(table["decision"], where),
                description=table["description"],
                terminal=terminal,
            )
        )

    policy = Policy(
        id=header["id"],
        version=header["version"],
        description=header["description"],
        rules=tuple(rules),
        default_decision=_decision(default["decision"], "default"),
        default_description=default["description"],
        default_rule_id=default["id"],
    )
    return replace(policy, hash=sha256_json(policy.to_dict()))


def load_policy_text(text: str, *, source: str = "<string>") -> Policy:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise PolicyError(f"{source}: invalid TOML: {error}") from None
    try:
        return parse_policy(data)
    except PolicyError as error:
        raise PolicyError(f"{source}: {error}") from None


def builtin_names() -> tuple[str, ...]:
    files = resources.files(BUILTIN_PACKAGE)
    return tuple(
        sorted(item.name.removesuffix(".toml") for item in files.iterdir() if item.name.endswith(".toml"))
    )


def load_builtin(name: str) -> Policy:
    if name not in builtin_names():
        raise PolicyError(f"unknown builtin policy {name!r}; known: {list(builtin_names())}")
    text = resources.files(BUILTIN_PACKAGE).joinpath(f"{name}.toml").read_text(encoding="utf-8")
    return load_policy_text(text, source=f"builtin:{name}")


def load_policy(name_or_path: str) -> Policy:
    """A builtin policy name, or a path to a .toml file."""

    if name_or_path in builtin_names():
        return load_builtin(name_or_path)
    path = Path(name_or_path)
    if path.suffix == ".toml" and path.is_file():
        return load_policy_text(path.read_text(encoding="utf-8"), source=str(path))
    raise PolicyError(
        f"{name_or_path!r} is neither a builtin policy {list(builtin_names())} nor a .toml file"
    )
