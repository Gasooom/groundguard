"""Frozen reference copy of the M2 provisional decision rules.

Copied verbatim from groundguard/pipeline.py at commit 019c1fd so the
builtin policy 'provisional-m2' can be checked against the original code
after the rules moved into TOML. Do not edit.
"""

PROVISIONAL_RULES = (
    ("safety.pii", "REJECT", "PII was detected in the answer."),
    ("safety.prompt_injection", "REJECT", "Prompt-injection patterns were detected in the answer."),
    ("grounding.contradicted", "REJECT", "At least one claim is contradicted by the evidence."),
    ("relevance.irrelevant", "REJECT", "The answer does not address the question."),
    ("grounding.none_supported", "REJECT", "No claim in the answer is supported by the evidence."),
    ("grounding.not_enough_info", "FLAG", "Some claims cannot be verified from the evidence."),
    ("default.accept", "ACCEPT", "Every claim is supported and no check failed."),
)


def provisional_decision(labels, *, relevant, pii_detected, injection_detected):
    fired = {
        "safety.pii": pii_detected,
        "safety.prompt_injection": injection_detected,
        "grounding.contradicted": "CONTRADICTED" in labels,
        "relevance.irrelevant": not relevant,
        "grounding.none_supported": "SUPPORTED" not in labels,
        "grounding.not_enough_info": "NOT_ENOUGH_INFO" in labels,
        "default.accept": True,
    }
    for rule, decision, reason in PROVISIONAL_RULES:
        if fired[rule]:
            return decision, rule, reason
    raise AssertionError("unreachable")
