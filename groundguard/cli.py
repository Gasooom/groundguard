"""GroundGuard command-line interface.

    groundguard bench run --dataset gg-legacy-v1 --input-mode context --out run.json
    groundguard bench compare BASELINE.json CANDIDATE.json --fail-on-regression
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from groundguard.bench import read_run, run_benchmark, write_run
from groundguard.bench.compare import compare_runs, format_comparison, parse_tolerances
from groundguard.bench.datasets import DATASETS
from groundguard.bench.errors import BenchmarkError
from groundguard.bench.runner import INPUT_MODES


def _summary(run: dict[str, object]) -> str:
    metrics = run["metrics"]
    assert isinstance(metrics, dict)
    lines = [f"predictions_hash: {run['predictions_hash']}"]
    for view in ("all", "dedup"):
        data = metrics[view]
        parts = []
        for name in ("grounding", "relevance", "contradiction"):
            rate = data[name]["accuracy"]
            parts.append(f"{name} {rate['numerator']}/{rate['denominator']}")
        far = data["decision"]["false_accept"]
        frr = data["decision"]["false_reject"]
        parts.append(f"FAR {far['numerator']}/{far['denominator']}")
        parts.append(f"FRR {frr['numerator']}/{frr['denominator']}")
        lines.append(f"{view:5}: " + ", ".join(parts))
    return "\n".join(lines)


def _bench_run(args: argparse.Namespace) -> int:
    run = run_benchmark(args.dataset, input_mode=args.input_mode)
    if args.out:
        write_run(run, Path(args.out))
        print(f"wrote {args.out}")
    print(_summary(run))
    return 0


def _bench_compare(args: argparse.Namespace) -> int:
    baseline = read_run(Path(args.baseline))
    candidate = read_run(Path(args.candidate))
    comparison = compare_runs(
        baseline,
        candidate,
        tolerances=parse_tolerances(args.max_drop or []),
    )
    print(format_comparison(comparison))
    if not comparison.comparable:
        return 2
    if args.fail_on_regression and comparison.regressions:
        print(f"FAILED: {len(comparison.regressions)} metric regression(s)")
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="groundguard")
    commands = parser.add_subparsers(dest="command", required=True)

    bench = commands.add_parser("bench", help="benchmark harness")
    bench_commands = bench.add_subparsers(dest="bench_command", required=True)

    run = bench_commands.add_parser("run", help="run a benchmark")
    run.add_argument("--dataset", required=True, choices=sorted(DATASETS))
    run.add_argument("--input-mode", required=True, choices=INPUT_MODES)
    run.add_argument("--out", help="write the run file to this path")
    run.set_defaults(handler=_bench_run)

    compare = bench_commands.add_parser("compare", help="compare two run files")
    compare.add_argument("baseline")
    compare.add_argument("candidate")
    compare.add_argument(
        "--fail-on-regression",
        action="store_true",
        help="exit 1 if any tracked metric is worse than its tolerance",
    )
    compare.add_argument(
        "--max-drop",
        action="append",
        metavar="METRIC=VALUE",
        help="allowed worsening for a metric, e.g. decision.false_accept=0.01 (default 0)",
    )
    compare.set_defaults(handler=_bench_compare)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except (BenchmarkError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
