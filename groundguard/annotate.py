"""Terminal review workflow for claim-level datasets.

    groundguard annotate status benchmark/datasets/gg-claims-v2/records.jsonl
    groundguard annotate review benchmark/datasets/gg-claims-v2/records.jsonl --reviewer gasim

``review`` walks through every NEEDS_REVIEW record. For each claim the
reviewer keeps or changes the drafted label (and can replace the evidence
quote); then keeps or changes relevance and completeness; then accepts the
record (LABELED), excludes it (EXCLUDED, with a reason) or marks it
uncertain. Every change is recorded in the record's notes. The file is
saved after each record, so a session can stop at any point.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from groundguard.bench.claims_dataset import AI_DRAFTER, parse_record, read_records, write_records
from groundguard.bench.errors import DatasetError


InputFn = Callable[[str], str]
OutputFn = Callable[[str], None]

_LABEL_KEYS = {"s": "SUPPORTED", "c": "CONTRADICTED", "n": "NOT_ENOUGH_INFO"}
_RELEVANCE_KEYS = {"r": "RELEVANT", "i": "IRRELEVANT"}
_COMPLETENESS_KEYS = {"c": "COMPLETE", "i": "INCOMPLETE", "x": "NOT_ASSESSED"}


class QuitReview(Exception):
    pass


def _atomic_write(path: Path, records: list[dict[str, Any]]) -> None:
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".records.", suffix=".tmp")
    os.close(descriptor)
    try:
        write_records(Path(temporary), records)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _ask(prompt: str, allowed: set[str], input_fn: InputFn) -> str:
    while True:
        answer = input_fn(prompt).strip().lower()
        if answer == "q":
            raise QuitReview
        if answer in allowed:
            return answer


def _show(raw: dict[str, Any], output: OutputFn) -> None:
    output("=" * 72)
    output(f"{raw['id']}  [{raw['domain']}]  group={raw['context_group']}  origin={raw['answer_origin']}")
    if raw.get("perturbation"):
        output(f"perturbation: {raw['perturbation']}")
    output(f"QUESTION: {raw['question']}")
    for source in raw["sources"]:
        output(f"SOURCE {source['id']} ({source['publisher']}, {source['url']}, retrieved {source['retrieved_at']}):")
        output(f"  {source['text']}")
    output(f"ANSWER: {raw['answer']}")


def review_record(raw: dict[str, Any], reviewer: str, input_fn: InputFn, output: OutputFn) -> dict[str, Any]:
    """Review one record interactively; return the updated raw record."""

    updated = {**raw, "claims": [dict(claim) for claim in raw["claims"]], "annotation": dict(raw["annotation"])}
    changes: list[str] = []
    _show(updated, output)
    source_text = {source["id"]: source["text"] for source in updated["sources"]}

    for claim in updated["claims"]:
        output(f"- {claim['id']}: {claim['text']}")
        output(f"  drafted label: {claim['label']}   phenomena: {', '.join(claim['phenomena'])}")
        for evidence in claim["evidence"]:
            output(f"  evidence [{evidence['source_id']}]: {evidence['quote']}")
        choice = _ask(
            "  [enter] keep, s/c/n set SUPPORTED/CONTRADICTED/NOT_ENOUGH_INFO, e edit evidence, q quit: ",
            {"", "s", "c", "n", "e"},
            input_fn,
        )
        if choice == "e":
            source_id = input_fn(f"  source id {sorted(source_text)}: ").strip()
            quote = input_fn("  exact quote: ").strip()
            if source_id not in source_text or not quote or quote not in source_text[source_id]:
                output("  ! not an exact substring of that source; evidence unchanged")
            else:
                claim["evidence"] = [{"source_id": source_id, "quote": quote}]
                changes.append(f"{claim['id']} evidence replaced")
            choice = _ask("  label: [enter] keep, s/c/n, q quit: ", {"", "s", "c", "n"}, input_fn)
        if choice in _LABEL_KEYS and _LABEL_KEYS[choice] != claim["label"]:
            changes.append(f"{claim['id']} {claim['label']} -> {_LABEL_KEYS[choice]}")
            claim["label"] = _LABEL_KEYS[choice]

    output(f"relevance: {updated['relevance']}   completeness: {updated['completeness']}")
    choice = _ask("  relevance: [enter] keep, r relevant, i irrelevant, q quit: ", {"", "r", "i"}, input_fn)
    if choice and _RELEVANCE_KEYS[choice] != updated["relevance"]:
        changes.append(f"relevance {updated['relevance']} -> {_RELEVANCE_KEYS[choice]}")
        updated["relevance"] = _RELEVANCE_KEYS[choice]
    choice = _ask(
        "  completeness: [enter] keep, c complete, i incomplete, x not assessed, q quit: ",
        {"", "c", "i", "x"},
        input_fn,
    )
    if choice and _COMPLETENESS_KEYS[choice] != updated["completeness"]:
        changes.append(f"completeness {updated['completeness']} -> {_COMPLETENESS_KEYS[choice]}")
        updated["completeness"] = _COMPLETENESS_KEYS[choice]

    decision = _ask("  a accept (LABELED), x exclude, u uncertain (accept + flag), q quit: ", {"a", "x", "u"}, input_fn)
    annotation = updated["annotation"]
    note = ""
    if decision in ("x", "u"):
        while not note:
            note = input_fn("  reason (required): ").strip()
    annotation.update(
        status="EXCLUDED" if decision == "x" else "LABELED",
        reviewed_by=reviewer,
        reviewed_at=datetime.now(timezone.utc).date().isoformat(),
        uncertain=decision == "u" or bool(annotation["uncertain"]),
    )
    if changes:
        annotation["label_basis"] = "judgment"
    review_note = "; ".join(filter(None, [f"review by {reviewer}: " + ("; ".join(changes) if changes else "no changes"), note]))
    annotation["notes"] = "; ".join(filter(None, [annotation.get("notes", ""), review_note]))

    parse_record(updated)  # validate before saving; raises with a precise message
    return updated


def review(path: Path, reviewer: str, *, input_fn: InputFn = input, output: OutputFn = print) -> Counter[str]:
    """Review all NEEDS_REVIEW records in ``path``. Returns a count of outcomes."""

    if not reviewer.strip() or reviewer == AI_DRAFTER:
        raise DatasetError("reviews must be recorded under a person's reviewer id")
    read_records(path)  # validate the whole file first
    raws = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    outcomes: Counter[str] = Counter()
    pending = [index for index, raw in enumerate(raws) if raw["annotation"]["status"] == "NEEDS_REVIEW"]
    output(f"{len(pending)} record(s) to review")
    for position, index in enumerate(pending, start=1):
        output(f"[{position}/{len(pending)}]")
        try:
            raws[index] = review_record(raws[index], reviewer, input_fn, output)
        except QuitReview:
            output("stopped; progress saved")
            break
        except DatasetError as error:
            output(f"! record not saved, validation failed: {error}")
            outcomes["invalid"] += 1
            continue
        outcomes[raws[index]["annotation"]["status"]] += 1
        _atomic_write(path, raws)
    return outcomes


def status(path: Path) -> dict[str, Any]:
    records = read_records(path)
    claims = [claim for record in records for claim in record.claims]
    return {
        "records": len(records),
        "by_status": dict(Counter(record.status for record in records)),
        "by_domain": dict(Counter(record.domain for record in records)),
        "by_origin": dict(Counter(record.answer_origin for record in records)),
        "context_groups": len({record.context_group for record in records}),
        "claims": len(claims),
        "claim_labels": dict(Counter(claim.label for claim in claims)),
        "phenomena": dict(Counter(p for claim in claims for p in claim.phenomena)),
    }
