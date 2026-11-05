import pytest

from groundguard.policy import (
    PolicyError,
    builtin_names,
    decide,
    load_builtin,
    load_policy,
    load_policy_text,
)
from groundguard.policy.facts import ClaimFact, EvaluationFacts


HEADER = '''
[policy]
id = "test"
version = "1.0.0"
description = "test policy"
'''
DEFAULT = '''
[default]
id = "default.accept"
decision = "ACCEPT"
description = "accept"
'''


def policy(rules=""):
    return load_policy_text(HEADER + rules + DEFAULT)


def facts(*claims, failed=()):
    return EvaluationFacts(
        claims=tuple(
            ClaimFact(label=label, confidence=confidence, signals=frozenset(signals))
            for label, confidence, signals in claims
        ),
        failed_checks=frozenset(failed),
    )


def claim(label, confidence=None, signals=()):
    return (label, confidence, signals)


# ------------------------------------------------------------------ loader


def test_builtins_load_and_have_stable_hashes():
    assert set(builtin_names()) == {"agent-default", "default", "provisional-m2", "strict", "v1-compat"}
    for name in builtin_names():
        loaded = load_builtin(name)
        assert loaded.id == name
        assert len(loaded.hash) == 64
        assert loaded.hash == load_builtin(name).hash


def test_hash_ignores_comments_and_formatting():
    rules = '''
[[rule]]
id = "r1"
when = { any_claim = "CONTRADICTED" }
decision = "REJECT"
description = "contradicted"
'''
    commented = rules.replace('[[rule]]', '# a comment\n[[rule]]').replace('"REJECT"', '"REJECT"   ')
    assert policy(rules).hash == policy(commented).hash
    assert policy(rules).hash != policy(rules.replace("contradicted", "changed")).hash


@pytest.mark.parametrize(
    "text, message",
    [
        ("not toml = = =", "invalid TOML"),
        (HEADER, "needs \\[policy\\] and \\[default\\]"),
        (HEADER + DEFAULT + "\n[extra]\nx = 1\n", "unknown top-level"),
        (HEADER.replace('version = "1.0.0"\n', "") + DEFAULT, "missing keys \\['version'\\]"),
        (HEADER + DEFAULT.replace('"ACCEPT"', '"MAYBE"'), "is not one of"),
        (HEADER + '[[rule]]\nid = "r"\nwhen = { eval = "x" }\ndecision = "REJECT"\ndescription = "d"\n' + DEFAULT,
         "unknown condition 'eval'"),
        (HEADER + '[[rule]]\nid = "r"\nwhen = { any_claim = "MAYBE" }\ndecision = "REJECT"\ndescription = "d"\n' + DEFAULT,
         "must be one of"),
        (HEADER + '[[rule]]\nid = "r"\nwhen = {}\ndecision = "REJECT"\ndescription = "d"\n' + DEFAULT,
         "non-empty table"),
        (HEADER + '[[rule]]\nid = "r"\nwhen = { min_confidence_below = 1.5 }\ndecision = "REJECT"\ndescription = "d"\n' + DEFAULT,
         "in \\[0, 1\\]"),
        (HEADER + '[[rule]]\nid = "r"\nwhen = { claim_fraction_above = { label = "SUPPORTED" } }\ndecision = "FLAG"\ndescription = "d"\n' + DEFAULT,
         "exactly 'label' and 'value'"),
        (HEADER + '[[rule]]\nid = "default.accept"\nwhen = { any_claim = "SUPPORTED" }\ndecision = "FLAG"\ndescription = "d"\n' + DEFAULT,
         "duplicate rule id"),
        (HEADER + '[[rule]]\nid = "r"\nwhen = { any_claim = "SUPPORTED" }\ndecision = "FLAG"\ndescription = "d"\nterminal = "yes"\n' + DEFAULT,
         "terminal"),
        (HEADER + '[[rule]]\nid = "r"\nwhen = { any_claim = "SUPPORTED" }\ndecision = "FLAG"\ndescription = "d"\nweight = 2\n' + DEFAULT,
         "unknown keys \\['weight'\\]"),
        (HEADER + '[[rule]]\nid = "r"\nwhen = { "v1.unsafe" = false }\ndecision = "REJECT"\ndescription = "d"\n' + DEFAULT,
         "must be true"),
    ],
)
def test_loader_rejects_invalid_policies(text, message):
    with pytest.raises(PolicyError, match=message):
        load_policy_text(text)


def test_load_policy_by_name_or_path(tmp_path):
    assert load_policy("strict").id == "strict"
    path = tmp_path / "mine.toml"
    path.write_text(HEADER + DEFAULT, encoding="utf-8")
    assert load_policy(str(path)).id == "test"
    with pytest.raises(PolicyError, match="neither a builtin"):
        load_policy("nope")


# ------------------------------------------------------------------ engine

RULES = '''
[[rule]]
id = "pii"
when = { check_failed = "pii" }
decision = "REJECT"
description = "pii"

[[rule]]
id = "contradicted"
when = { any_claim = "CONTRADICTED" }
decision = "REJECT"
description = "contradicted"

[[rule]]
id = "note.qualifier"
when = { any_signal = "qualifier" }
decision = "FLAG"
description = "annotation only"
terminal = false

[[rule]]
id = "mostly_unverified"
when = { claim_fraction_above = { label = "NOT_ENOUGH_INFO", value = 0.5 } }
decision = "REJECT"
description = "mostly unverified"

[[rule]]
id = "low_confidence"
when = { min_confidence_below = 0.6 }
decision = "HUMAN_REVIEW"
description = "low confidence"

[[rule]]
id = "some_nei_and_irrelevant"
when = { any_claim = "NOT_ENOUGH_INFO", check_failed = "relevance" }
decision = "REJECT"
description = "both"
'''


def test_first_terminal_rule_decides_and_all_matches_are_recorded():
    result = decide(
        policy(RULES),
        facts(claim("CONTRADICTED"), claim("NOT_ENOUGH_INFO", signals=("qualifier",)), failed=("pii",)),
    )
    assert (result.decision, result.rule) == ("REJECT", "pii")
    assert result.matched_rules == ("pii", "contradicted", "note.qualifier")
    assert result.annotations == ("note.qualifier",)
    assert result.policy_id == "test" and len(result.policy_hash) == 64


def test_non_terminal_rules_never_decide():
    result = decide(policy(RULES), facts(claim("SUPPORTED", signals=("qualifier",))))
    assert (result.decision, result.rule) == ("ACCEPT", "default.accept")
    assert result.annotations == ("note.qualifier",)


def test_claim_fraction_above_is_strict_and_false_without_claims():
    p = policy(RULES)
    assert decide(p, facts(claim("NOT_ENOUGH_INFO"), claim("SUPPORTED"))).rule == "default.accept"
    assert decide(p, facts(claim("NOT_ENOUGH_INFO"), claim("NOT_ENOUGH_INFO"), claim("SUPPORTED"))).rule == "mostly_unverified"
    assert decide(p, facts()).rule == "default.accept"


def test_min_confidence_never_fires_for_uncalibrated_claims():
    p = policy(RULES)
    assert decide(p, facts(claim("SUPPORTED", confidence=None))).rule == "default.accept"
    assert decide(p, facts(claim("SUPPORTED", confidence=0.9), claim("SUPPORTED", confidence=None))).rule == "default.accept"
    assert decide(p, facts(claim("SUPPORTED", confidence=0.55), claim("SUPPORTED", confidence=None))).rule == "low_confidence"


def test_conditions_in_one_rule_are_combined_with_and():
    p = policy(RULES)
    assert decide(p, facts(claim("SUPPORTED"), claim("SUPPORTED"), claim("NOT_ENOUGH_INFO"))).rule == "default.accept"
    combined = decide(p, facts(claim("SUPPORTED"), claim("SUPPORTED"), claim("NOT_ENOUGH_INFO"), failed=("relevance",)))
    assert combined.rule == "some_nei_and_irrelevant"


def test_no_claim_holds_when_there_are_no_claims():
    p = policy('''
[[rule]]
id = "none_supported"
when = { no_claim = "SUPPORTED" }
decision = "REJECT"
description = "none"
''')
    assert decide(p, facts()).rule == "none_supported"
    assert decide(p, facts(claim("SUPPORTED"))).rule == "default.accept"


def test_v1_conditions_require_v1_facts():
    with pytest.raises(PolicyError, match="needs v1 facts"):
        decide(load_builtin("v1-compat"), facts(claim("SUPPORTED")))


def test_default_policy_sends_qualifier_mismatch_to_human_review():
    default = load_builtin("default")
    result = decide(default, facts(claim("SUPPORTED"), claim("NOT_ENOUGH_INFO", signals=("qualifier",))))
    assert (result.decision, result.rule) == ("HUMAN_REVIEW", "grounding.qualifier_mismatch")
    # Contradiction still outranks it.
    result = decide(default, facts(claim("CONTRADICTED"), claim("NOT_ENOUGH_INFO", signals=("qualifier",))))
    assert result.decision == "REJECT"


def test_strict_policy_rejects_any_unverifiable_claim():
    result = decide(load_builtin("strict"), facts(claim("SUPPORTED"), claim("NOT_ENOUGH_INFO")))
    assert (result.decision, result.rule) == ("REJECT", "grounding.not_enough_info")
