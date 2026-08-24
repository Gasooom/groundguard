from pathlib import Path

from groundguard.application.evaluator import evaluate
from groundguard.evaluation.evaluation_record import (
    EvaluationRecord,
)
from groundguard.storage.evaluation_store import (
    EvaluationStore,
)


def make_record() -> EvaluationRecord:
    result = evaluate(
        question="When was the company founded?",
        context="The company was founded in 2018.",
        answer="The company was founded in 2018.",
    )

    return EvaluationRecord.from_evaluation(
        question="When was the company founded?",
        context="The company was founded in 2018.",
        answer="The company was founded in 2018.",
        result=result,
    )


def test_save_and_get_by_id(tmp_path: Path):
    store = EvaluationStore(
        tmp_path / "groundguard.db"
    )

    record = make_record()

    evaluation_id = store.save(record)

    result = store.get_by_id(evaluation_id)

    assert result is not None
    assert result["id"] == evaluation_id
    assert result["system_decision"] == "ACCEPT"
    assert result["reliability_score"] == 1.0


def test_get_all_returns_saved_records(
    tmp_path: Path,
):
    store = EvaluationStore(
        tmp_path / "groundguard.db"
    )

    first_id = store.save(make_record())
    second_id = store.save(make_record())

    records = store.get_all()

    assert len(records) == 2
    assert {
        record["id"]
        for record in records
    } == {
        first_id,
        second_id,
    }


def test_count_returns_number_of_records(
    tmp_path: Path,
):
    store = EvaluationStore(
        tmp_path / "groundguard.db"
    )

    assert store.count() == 0

    store.save(make_record())
    store.save(make_record())

    assert store.count() == 2


def test_get_by_id_returns_none_for_missing_record(
    tmp_path: Path,
):
    store = EvaluationStore(
        tmp_path / "groundguard.db"
    )

    assert store.get_by_id("missing") is None


def test_clear_removes_all_records(
    tmp_path: Path,
):
    store = EvaluationStore(
        tmp_path / "groundguard.db"
    )

    store.save(make_record())
    store.save(make_record())

    assert store.count() == 2

    store.clear()

    assert store.count() == 0
    assert store.get_all() == []


def test_records_persist_across_store_instances(
    tmp_path: Path,
):
    database = tmp_path / "groundguard.db"

    first_store = EvaluationStore(database)

    evaluation_id = first_store.save(
        make_record()
    )

    second_store = EvaluationStore(database)

    result = second_store.get_by_id(
        evaluation_id
    )

    assert result is not None
    assert result["id"] == evaluation_id