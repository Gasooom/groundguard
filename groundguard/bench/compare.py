"""Compare two benchmark run files and detect regressions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping


Direction = Literal["higher_is_better", "lower_is_better"]

# Metric path (relative to a view) → direction.
TRACKED_METRICS: dict[str, Direction] = {
    "grounding.accuracy": "higher_is_better",
    "relevance.accuracy": "higher_is_better",
    "contradiction.accuracy": "higher_is_better",
    "grounding.macro_f1": "higher_is_better",
    "relevance.macro_f1": "higher_is_better",
    "contradiction.macro_f1": "higher_is_better",
    "decision.false_accept": "lower_is_better",
    "decision.false_reject": "lower_is_better",
}

TRACKED_VIEWS = ("all", "dedup")

PREDICTION_FIELDS = (
    "grounding_label",
    "relevance_label",
    "contradiction_label",
    "system_decision",
)


@dataclass(frozen=True)
class MetricDelta:
    view: str
    metric: str
    direction: Direction
    baseline: float | None
    candidate: float | None
    tolerance: float

    @property
    def delta(self) -> float | None:
        if self.baseline is None or self.candidate is None:
            return None
        return self.candidate - self.baseline

    @property
    def regressed(self) -> bool:
        delta = self.delta
        if delta is None:
            return self.baseline is not None and self.candidate is None
        worse_by = -delta if self.direction == "higher_is_better" else delta
        return worse_by > self.tolerance + 1e-12


@dataclass(frozen=True)
class Flip:
    id: str
    field: str
    baseline: str
    candidate: str


@dataclass(frozen=True)
class Comparison:
    deltas: tuple[MetricDelta, ...]
    flips: tuple[Flip, ...]
    comparable: bool
    notes: tuple[str, ...]

    @property
    def regressions(self) -> tuple[MetricDelta, ...]:
        return tuple(delta for delta in self.deltas if delta.regressed)


def _metric_value(view: Mapping[str, Any], path: str) -> float | None:
    node: Any = view
    for part in path.split("."):
        if not isinstance(node, Mapping) or part not in node:
            return None
        node = node[part]
    if isinstance(node, Mapping):
        node = node.get("value")
    if node is None or isinstance(node, (int, float)):
        return None if node is None else float(node)
    return None


def parse_tolerances(specs: list[str]) -> dict[str, float]:
    """Parse ``metric=tolerance`` pairs, e.g. ``decision.false_accept=0.01``."""

    tolerances: dict[str, float] = {}
    for spec in specs:
        name, separator, value = spec.partition("=")
        if not separator or name not in TRACKED_METRICS:
            raise ValueError(
                f"invalid tolerance {spec!r}; expected METRIC=VALUE with METRIC in "
                f"{sorted(TRACKED_METRICS)}"
            )
        tolerance = float(value)
        if tolerance < 0:
            raise ValueError("tolerances must be non-negative")
        tolerances[name] = tolerance
    return tolerances


def compare_runs(
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
    *,
    tolerances: Mapping[str, float] | None = None,
) -> Comparison:
    tolerances = dict(tolerances or {})
    notes: list[str] = []

    base_dataset = baseline["manifest"]["dataset"]
    cand_dataset = candidate["manifest"]["dataset"]
    comparable = (
        base_dataset["id"] == cand_dataset["id"]
        and base_dataset["version"] == cand_dataset["version"]
    )
    if not comparable:
        notes.append(
            "runs use different datasets "
            f"({base_dataset['id']}@{base_dataset['version']} vs "
            f"{cand_dataset['id']}@{cand_dataset['version']}); metric deltas are not meaningful"
        )
    elif base_dataset["sha256"] != cand_dataset["sha256"]:
        notes.append("dataset files changed between runs (sha256 differs)")

    if baseline["manifest"]["config"] != candidate["manifest"]["config"]:
        notes.append("run configurations differ")

    deltas: list[MetricDelta] = []
    for view in TRACKED_VIEWS:
        base_view = baseline["metrics"].get(view, {})
        cand_view = candidate["metrics"].get(view, {})
        for metric, direction in TRACKED_METRICS.items():
            deltas.append(
                MetricDelta(
                    view=view,
                    metric=metric,
                    direction=direction,
                    baseline=_metric_value(base_view, metric),
                    candidate=_metric_value(cand_view, metric),
                    tolerance=tolerances.get(metric, 0.0),
                )
            )

    base_predictions = {item["id"]: item for item in baseline["predictions"]}
    flips: list[Flip] = []
    for item in candidate["predictions"]:
        previous = base_predictions.get(item["id"])
        if previous is None:
            continue
        for field in PREDICTION_FIELDS:
            if previous[field] != item[field]:
                flips.append(Flip(item["id"], field, previous[field], item[field]))

    return Comparison(
        deltas=tuple(deltas),
        flips=tuple(flips),
        comparable=comparable,
        notes=tuple(notes),
    )


def format_comparison(comparison: Comparison) -> str:
    lines: list[str] = []
    for note in comparison.notes:
        lines.append(f"NOTE: {note}")
    lines.append(f"{'view':6} {'metric':26} {'baseline':>9} {'candidate':>9} {'delta':>9}  status")
    for delta in comparison.deltas:
        def fmt(value: float | None) -> str:
            return "n/a" if value is None else f"{value:.4f}"

        status = "REGRESSION" if delta.regressed else "ok"
        lines.append(
            f"{delta.view:6} {delta.metric:26} {fmt(delta.baseline):>9} "
            f"{fmt(delta.candidate):>9} {fmt(delta.delta):>9}  {status}"
        )
    lines.append(f"prediction flips: {len(comparison.flips)}")
    for flip in comparison.flips[:50]:
        lines.append(f"  {flip.id}: {flip.field} {flip.baseline} -> {flip.candidate}")
    if len(comparison.flips) > 50:
        lines.append(f"  … {len(comparison.flips) - 50} more")
    return "\n".join(lines)
