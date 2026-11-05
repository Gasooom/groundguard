"""Benchmark the v2 engine on a claim-level dataset (gg-claims-v2 format).

Two measurements, reported separately:

claim level (oracle segmentation)
    Every gold claim is verified directly by the verifier chain against
    candidates selected from the record's sources. This isolates verifier
    quality from segmentation. It also measures *evidence localization*:
    for correctly labeled SUPPORTED/CONTRADICTED claims, whether the cited
    evidence overlaps the annotator's quote.
answer level (end to end)
    The full pipeline runs on the answer, with segmentation, verification
    and policy, and the decision is scored against acceptability@1: an answer
    is good iff it is relevant and every gold claim is SUPPORTED.

Splits: ``dev``/``test``/``all`` need a frozen dataset. Every test run is
appended to the test-access log with a stated purpose. ``unreviewed`` runs
on every record regardless of review status, for development only; such
runs are labelled ``label_status = "unreviewed"`` and must not be reported
as results.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Sequence

from groundguard.calibration import CalibrationSet
from groundguard.bench.claims_dataset import ClaimRecord, load_split, log_test_access, read_records
from groundguard.bench.errors import DatasetError
from groundguard.bench.manifest import RUN_FILE_SCHEMA_VERSION, build_manifest
from groundguard.bench.metrics import (
    Rate,
    accuracy,
    bootstrap_ci,
    confusion_matrix,
    decision_rates,
    macro_f1,
    per_label_scores,
    wilson_interval,
)
from groundguard.core.serialization import sha256_json
from groundguard.core.types import VERDICT_LABELS, Claim, SourceDocument, Span
from groundguard.evidence.bm25 import select_evidence
from groundguard.evidence.chunking import chunk_sources
from groundguard.pipeline import ENGINE_VERSION, PipelineConfig, evaluate_v2
from groundguard.policy import DEFAULT_POLICY, Policy, load_builtin


ClaimsSplit = Literal["dev", "test", "all", "unreviewed"]
DECISIONS = ("ACCEPT", "FLAG", "REJECT", "HUMAN_REVIEW")


@dataclass(frozen=True)
class _DatasetInfo:
    id: str
    version: str
    sha256: str
    files: tuple[str, ...]
    size: int

    def __len__(self) -> int:
        return self.size


def _load(records_path: Path, split: ClaimsSplit) -> tuple[tuple[ClaimRecord, ...], str]:
    if split == "unreviewed":
        return read_records(records_path), "unreviewed"
    records = load_split(records_path, split)
    return records, "reviewed"


def _normalize_quote(text: str) -> str:
    return " ".join(text.strip().rstrip(".!?").split()).lower()


def _evidence_hit(predicted: Sequence[str], gold: Sequence[str]) -> bool:
    for left in map(_normalize_quote, predicted):
        for right in map(_normalize_quote, gold):
            if left and right and (left in right or right in left):
                return True
    return False


def _rate(rate: Rate, groups: Sequence[str], statistic: Any) -> dict[str, Any]:
    data = rate.to_dict()
    interval = wilson_interval(rate.numerator, rate.denominator)
    data["wilson_95"] = None if interval is None else [round(interval[0], 6), round(interval[1], 6)]
    boot = bootstrap_ci(groups, statistic, n_resamples=2000, seed=0)
    data["group_bootstrap_95"] = None if boot is None else [round(boot[0], 6), round(boot[1], 6)]
    return data


def _claim_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"claims": 0}
    gold = [row["gold"] for row in rows]
    predicted = [row["predicted"] for row in rows]
    groups = [row["group"] for row in rows]

    def accuracy_on(indices: Sequence[int]) -> float | None:
        return sum(gold[i] == predicted[i] for i in indices) / len(indices) if indices else None

    scores = per_label_scores(gold, predicted, VERDICT_LABELS)
    f1 = macro_f1(scores)
    localizable = [row for row in rows if row["gold"] == row["predicted"] and row["gold"] != "NOT_ENOUGH_INFO"]
    by_phenomenon: dict[str, dict[str, Any]] = {}
    for phenomenon in sorted({p for row in rows for p in row["phenomena"]}):
        subset = [row for row in rows if phenomenon in row["phenomena"]]
        contradicted = [row for row in subset if row["gold"] == "CONTRADICTED"]
        by_phenomenon[phenomenon] = {
            "claims": len(subset),
            "accuracy": Rate(sum(r["gold"] == r["predicted"] for r in subset), len(subset)).to_dict(),
            "contradicted_recall": Rate(
                sum(r["predicted"] == "CONTRADICTED" for r in contradicted), len(contradicted)
            ).to_dict(),
        }
    return {
        "claims": len(rows),
        "context_groups": len(set(groups)),
        "accuracy": _rate(accuracy(gold, predicted), groups, accuracy_on),
        "macro_f1": None if f1 is None else round(f1, 6),
        "per_label": {label: score.to_dict() for label, score in scores.items()},
        "confusion_matrix": confusion_matrix(gold, predicted, VERDICT_LABELS),
        "evidence_localization": Rate(sum(row["evidence_hit"] for row in localizable), len(localizable)).to_dict(),
        "by_phenomenon": by_phenomenon,
    }


def _answer_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"answers": 0}
    good = [row["good"] for row in rows]
    decisions = [row["decision"] for row in rows]
    groups = [row["group"] for row in rows]
    rates = decision_rates(good, decisions)

    def far_on(indices: Sequence[int]) -> float | None:
        bad = [i for i in indices if not good[i]]
        return sum(decisions[i] == "ACCEPT" for i in bad) / len(bad) if bad else None

    def frr_on(indices: Sequence[int]) -> float | None:
        ok = [i for i in indices if good[i]]
        return sum(decisions[i] != "ACCEPT" for i in ok) / len(ok) if ok else None

    def review_on(indices: Sequence[int]) -> float | None:
        return sum(decisions[i] == "HUMAN_REVIEW" for i in indices) / len(indices) if indices else None

    bad_auto = [i for i in range(len(rows)) if not good[i] and decisions[i] != "HUMAN_REVIEW"]

    def far_auto_on(indices: Sequence[int]) -> float | None:
        bad = [i for i in indices if not good[i] and decisions[i] != "HUMAN_REVIEW"]
        return sum(decisions[i] == "ACCEPT" for i in bad) / len(bad) if bad else None

    return {
        "answers": len(rows),
        "acceptability": "acceptability@1 without safety: good iff relevant and every gold claim SUPPORTED",
        "distribution": {label: decisions.count(label) for label in DECISIONS},
        "false_accept": _rate(rates.false_accept, groups, far_on),
        "false_reject": _rate(rates.false_reject, groups, frr_on),
        "review_rate": _rate(Rate(decisions.count("HUMAN_REVIEW"), len(rows)), groups, review_on),
        "false_accept_among_auto_decided": _rate(
            Rate(sum(decisions[i] == "ACCEPT" for i in bad_auto), len(bad_auto)), groups, far_auto_on
        ),
    }


def run_claims_benchmark(
    records_path: Path,
    *,
    split: ClaimsSplit,
    dataset_id: str,
    pipeline_config: PipelineConfig | None = None,
    policy: Policy | None = None,
    purpose: str | None = None,
    test_access_log: Path | None = None,
    calibration: CalibrationSet | None = None,
) -> dict[str, Any]:
    if split == "test":
        if test_access_log is None or not (purpose or "").strip():
            raise DatasetError("a test-split run needs --purpose and a test access log")
    config = pipeline_config or PipelineConfig()
    policy = policy or load_builtin(DEFAULT_POLICY)
    records, label_status = _load(records_path, split)
    if not records:
        raise DatasetError(f"no records in split {split!r}")
    chain = config.chain()

    claim_rows: list[dict[str, Any]] = []
    answer_rows: list[dict[str, Any]] = []
    predictions: list[dict[str, Any]] = []
    for record in records:
        sources = [SourceDocument(id=source.id, text=source.text) for source in record.sources]
        chunks = chunk_sources(sources)
        claim_predictions = []
        for gold in record.claims:
            claim = Claim(id=gold.id, text=gold.text, answer_span=Span(*gold.answer_span), origin="sentence")
            verdict = chain.verify(claim, select_evidence(gold.text, chunks, top_k=config.top_k))
            if calibration is not None:
                verdict = calibration.apply(verdict)
            hit = _evidence_hit([item.text for item in verdict.evidence], [item.quote for item in gold.evidence])
            claim_rows.append(
                {"gold": gold.label, "predicted": verdict.label, "group": record.context_group,
                 "phenomena": gold.phenomena, "evidence_hit": hit}
            )
            claim_predictions.append(
                {"id": gold.id, "gold": gold.label, "label": verdict.label, "verifier": verdict.verifier,
                 "raw_score": round(verdict.raw_score, 6), "confidence": verdict.confidence,
                 "evidence_hit": hit}
            )
        report = evaluate_v2(
            question=record.question, answer=record.answer, contexts=sources, config=config,
            policy=policy, calibration=calibration,
        )
        answer_rows.append(
            {"good": record.is_good, "decision": report.decision.decision, "group": record.context_group}
        )
        predictions.append(
            {"id": record.id, "claims": claim_predictions, "decision": report.decision.decision,
             "rule": report.decision.rule}
        )

    by_domain: dict[str, list[int]] = defaultdict(list)
    for index, record in enumerate(records):
        by_domain[record.domain].append(index)

    run_config = {
        "engine": "v2",
        "engine_version": ENGINE_VERSION,
        "split": split,
        "label_status": label_status,
        "pipeline": config.to_dict(),
        "verifier_chain": list(chain.ids),
        "policy": {"id": policy.id, "version": policy.version, "hash": policy.hash},
        "calibration_hash": None if calibration is None else calibration.hash,
    }
    info = _DatasetInfo(
        id=dataset_id,
        version=_dataset_version(records_path),
        sha256=hashlib.sha256(records_path.read_bytes()).hexdigest(),
        files=(records_path.as_posix(),),
        size=len(records),
    )
    owners = _owners(records)
    metrics: dict[str, Any] = {
        "all": {"claim_level": _claim_metrics(claim_rows), "answer_level": _answer_metrics(answer_rows)}
    }
    for domain, indices in sorted(by_domain.items()):
        domain_claims = [row for row, owner in zip(claim_rows, owners) if records[owner].domain == domain]
        metrics[f"domain={domain}"] = {
            "claim_level": _claim_metrics(domain_claims),
            "answer_level": _answer_metrics([answer_rows[i] for i in indices]),
        }

    predictions_digest = sha256_json(predictions)
    run: dict[str, Any] = {
        "schema_version": RUN_FILE_SCHEMA_VERSION,
        "kind": "claims",
        "manifest": build_manifest(info, run_config),
        "metrics": metrics,
        "predictions_hash": predictions_digest,
        "predictions": predictions,
    }
    if split == "test":
        assert test_access_log is not None and purpose is not None
        log_test_access(
            test_access_log,
            dataset=dataset_id,
            version=info.version,
            purpose=purpose,
            run_id=predictions_digest[:16],
        )
    return run


def _owners(records: Sequence[ClaimRecord]) -> list[int]:
    """Record index for each claim row, in claim order."""

    return [index for index, record in enumerate(records) for _ in record.claims]


def _dataset_version(records_path: Path) -> str:
    splits = records_path.parent / "splits.json"
    if splits.exists():
        return str(json.loads(splits.read_text(encoding="utf-8"))["version"])
    return "unfrozen"
