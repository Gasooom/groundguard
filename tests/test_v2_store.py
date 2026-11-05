import json
import sqlite3

import pytest

from groundguard.pipeline import evaluate_v2
from groundguard.storage.v2_store import V2Store, redact_text


def report(answer="Acme was founded in 2010.", context="Acme was founded in 2010."):
    return evaluate_v2(question="When was Acme founded?", context=context, answer=answer).to_dict()


@pytest.fixture
def store(tmp_path):
    return V2Store(tmp_path / "gg.db")


def test_migrations_are_recorded_and_idempotent(tmp_path):
    path = tmp_path / "gg.db"
    first = V2Store(path)
    assert first.schema_version() == 2
    assert first.migrate() == []
    with sqlite3.connect(path) as connection:
        versions = [row[0] for row in connection.execute("SELECT version FROM schema_migrations ORDER BY version")]
    assert versions == [1, 2]


def test_v2_store_leaves_the_v1_table_alone(tmp_path):
    from groundguard.storage import EvaluationStore

    path = tmp_path / "gg.db"
    EvaluationStore(path)
    V2Store(path)
    with sqlite3.connect(path) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"evaluations", "evaluations_v2", "api_keys", "schema_migrations"} <= tables


def test_api_keys_hash_authenticate_and_revoke(store):
    key = store.create_api_key("tenant-a", label="ci")
    prefix, key_id, secret = key.split("_", 2)
    assert prefix == "gg" and len(secret) >= 32
    assert store.authenticate(key) == "tenant-a"

    with sqlite3.connect(store.database_path) as connection:
        (stored,) = connection.execute("SELECT secret_hash FROM api_keys").fetchone()
    assert secret not in stored  # only the hash is stored

    for bad in ("", "gg__x", f"gg_{key_id}_wrong", f"xx_{key_id}_{secret}", f"gg_unknown_{secret}"):
        assert store.authenticate(bad) is None
    assert store.revoke_api_key(key_id) is True
    assert store.authenticate(key) is None
    assert store.revoke_api_key(key_id) is False
    with pytest.raises(ValueError):
        store.create_api_key(" ")


def test_evaluations_are_tenant_scoped(store):
    evaluation_id = store.save_evaluation("tenant-a", report(), "full")
    assert store.get_evaluation("tenant-a", evaluation_id)["decision"] == "ACCEPT"
    assert store.get_evaluation("tenant-b", evaluation_id) is None
    assert store.list_evaluations("tenant-b") == []
    assert store.stats("tenant-b")["total"] == 0


def test_payload_modes(store):
    answer = "Acme was founded in 2010. Email jane.doe@example.com for details."
    full = store.get_evaluation("t", store.save_evaluation("t", report(answer), "full"))
    redacted = store.get_evaluation("t", store.save_evaluation("t", report(answer), "redacted"))
    minimal = store.get_evaluation("t", store.save_evaluation("t", report(answer), "none"))

    assert "jane.doe@example.com" in json.dumps(full["report"])
    assert "jane.doe@example.com" not in json.dumps(redacted["report"])
    assert "[REDACTED]" in redacted["report"]["answer"]
    assert "answer" not in minimal["report"] and "question" not in minimal["report"]
    assert "jane.doe@example.com" not in json.dumps(minimal["report"])
    assert minimal["report"]["decision"]["decision"] == "REJECT"
    assert {full["payload_mode"], redacted["payload_mode"], minimal["payload_mode"]} == {"full", "redacted", "none"}
    with pytest.raises(ValueError):
        store.save_evaluation("t", report(), "everything")


def test_redact_text_prefers_longest_match():
    text = "Card 4111 1111 1111 1111, call 555-123-4567."
    assert redact_text(text) == "Card [REDACTED], call [REDACTED]."


def test_list_pagination_cursor_and_filters(store):
    ids = [store.save_evaluation("t", report(), "none") for _ in range(5)]
    store.save_evaluation("t", report(answer="Acme was founded in 1999."), "none")

    page = store.list_evaluations("t", limit=3)
    assert len(page) == 3
    rest = store.list_evaluations("t", limit=10, before=(page[-1]["created_at"], page[-1]["id"]))
    assert len(page) + len(rest) == 6
    assert {row["id"] for row in page}.isdisjoint({row["id"] for row in rest})
    assert set(ids) <= {row["id"] for row in page + rest}
    assert all("report" not in row for row in page)

    rejected = store.list_evaluations("t", decision="REJECT")
    assert len(rejected) == 1 and rejected[0]["rule"] == "grounding.contradicted"
    with pytest.raises(ValueError):
        store.list_evaluations("t", decision="MAYBE")
    with pytest.raises(ValueError):
        store.list_evaluations("t", limit=0)


def test_stats_are_computed_in_sql(store):
    store.save_evaluation("t", report(), "none")
    store.save_evaluation("t", report(), "none")
    store.save_evaluation("t", report(answer="Acme was founded in 1999."), "none")
    stats = store.stats("t")
    assert stats["total"] == 3
    assert stats["decisions"] == {"ACCEPT": 2, "FLAG": 0, "REJECT": 1, "HUMAN_REVIEW": 0}
    assert stats["decision_rates"]["ACCEPT"] == pytest.approx(2 / 3, abs=1e-6)
    assert stats["contradicted_claims"] == 1
    assert stats["by_rule"] == {"default.accept": 2, "grounding.contradicted": 1}
    assert len(stats["by_day"]) == 1 and stats["by_day"][0]["ACCEPT"] == 2
    assert store.stats("t", since="2999-01-01")["total"] == 0
