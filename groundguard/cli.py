"""GroundGuard command-line interface.

    groundguard bench run --dataset gg-legacy-v1 --input-mode context --out run.json
    groundguard bench compare BASELINE.json CANDIDATE.json --fail-on-regression
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from groundguard.annotate import review
from groundguard.annotate import status as annotation_status
from groundguard.bench import read_run, run_benchmark, write_run
from groundguard.bench.claims_dataset import freeze
from groundguard.bench.claims_runner import run_claims_benchmark
from groundguard.calibration import calibration_report, fit_calibration, load_calibration
from groundguard.bench.compare import compare_runs, format_comparison, parse_tolerances
from groundguard.bench.datasets import DATASETS
from groundguard.bench.errors import BenchmarkError
from groundguard.bench.runner import INPUT_MODES
from groundguard.core.errors import GroundGuardError
from groundguard.core.types import GRANULARITIES
from groundguard.pipeline import PipelineConfig
from groundguard.policy import builtin_names, load_policy


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
    pipeline_config = None
    if args.engine == "v2":
        pipeline_config = PipelineConfig(
            granularity=args.granularity,
            guards=not args.no_guards,
            structured_facts=not args.no_structured_facts,
            lexical_mode=args.lexical_mode,
            lexical_threshold=args.lexical_threshold,
        )
    elif any(
        (args.granularity != "conjunct", args.no_guards, args.no_structured_facts,
         args.lexical_mode != "content", args.lexical_threshold != 1.0, args.policy is not None)
    ):
        raise ValueError("pipeline options only apply to --engine v2")
    run = run_benchmark(
        args.dataset,
        input_mode=args.input_mode,
        engine=args.engine,
        pipeline_config=pipeline_config,
        policy=None if args.policy is None else load_policy(args.policy),
    )
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


def _policy_check(args: argparse.Namespace) -> int:
    loaded = load_policy(args.policy)
    print(f"{loaded.id} {loaded.version}  sha256:{loaded.hash}")
    print(f"  {loaded.description}")
    for index, rule in enumerate(loaded.rules, start=1):
        conditions = " AND ".join(f"{c.kind}={c.value}" for c in rule.when)
        marker = "" if rule.terminal else "  (non-terminal)"
        print(f"  {index}. {rule.id}: {conditions} -> {rule.decision}{marker}")
    print(f"  default: {loaded.default_rule_id} -> {loaded.default_decision}")
    return 0


def _policy_list(args: argparse.Namespace) -> int:
    for name in builtin_names():
        loaded = load_policy(name)
        print(f"{loaded.id:16} {loaded.version:8} {loaded.hash[:12]}  {loaded.description}")
    return 0


def _bench_claims(args: argparse.Namespace) -> int:
    run = run_claims_benchmark(
        Path(args.records),
        split=args.split,
        dataset_id=args.dataset_id,
        policy=None if args.policy is None else load_policy(args.policy),
        purpose=args.purpose,
        test_access_log=Path(args.test_access_log),
        calibration=None if args.calibration is None else load_calibration(Path(args.calibration)),
    )
    if args.out:
        write_run(run, Path(args.out))
        print(f"wrote {args.out}")
    if run["manifest"]["config"]["label_status"] == "unreviewed":
        print("WARNING: unreviewed labels; development use only, not a result")
    claim = run["metrics"]["all"]["claim_level"]
    answer = run["metrics"]["all"]["answer_level"]
    acc, far, frr = claim["accuracy"], answer["false_accept"], answer["false_reject"]
    print(f"claims: accuracy {acc['numerator']}/{acc['denominator']}, macro-F1 {claim['macro_f1']}")
    print(f"answers: FAR {far['numerator']}/{far['denominator']}, FRR {frr['numerator']}/{frr['denominator']}, "
          f"review {answer['review_rate']['numerator']}/{answer['review_rate']['denominator']}")
    return 0


def _calibrate_fit(args: argparse.Namespace) -> int:
    calibration = fit_calibration(
        read_run(Path(args.run)),
        method=args.method,
        min_samples=args.min_samples,
        allow_unreviewed=args.allow_unreviewed,
    )
    calibration.save(Path(args.out))
    print(f"wrote {args.out}: {len(calibration.calibrators)} calibrator(s), skipped {calibration.fitted_on['skipped']}")
    return 0


def _calibrate_report(args: argparse.Namespace) -> int:
    report = calibration_report(read_run(Path(args.run)), load_calibration(Path(args.calibration)))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


def _annotate_review(args: argparse.Namespace) -> int:
    outcomes = review(Path(args.records), args.reviewer)
    print(f"reviewed: {dict(outcomes)}")
    return 0


def _annotate_status(args: argparse.Namespace) -> int:
    print(json.dumps(annotation_status(Path(args.records)), indent=2, sort_keys=True))
    return 0


def _annotate_freeze(args: argparse.Namespace) -> int:
    manifest = freeze(Path(args.records), version=args.version)
    print(f"frozen {args.version}: {manifest['counts']} (excluded {len(manifest['excluded'])})")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="groundguard")
    commands = parser.add_subparsers(dest="command", required=True)

    bench = commands.add_parser("bench", help="benchmark harness")
    bench_commands = bench.add_subparsers(dest="bench_command", required=True)

    run = bench_commands.add_parser("run", help="run a benchmark")
    run.add_argument("--dataset", required=True, choices=sorted(DATASETS))
    run.add_argument("--input-mode", required=True, choices=INPUT_MODES)
    run.add_argument("--engine", choices=("v1", "v2"), default="v1")
    run.add_argument("--granularity", choices=GRANULARITIES, default="conjunct", help="v2 only")
    run.add_argument("--lexical-mode", choices=("content", "v1"), default="content", help="v2 only")
    run.add_argument("--lexical-threshold", type=float, default=1.0, help="v2 only")
    run.add_argument("--no-guards", action="store_true", help="v2 only: disable the guard verifier")
    run.add_argument("--no-structured-facts", action="store_true", help="v2 only")
    run.add_argument("--policy", help="v2 only: builtin policy name or path to a .toml policy")
    run.add_argument("--out", help="write the run file to this path")
    run.set_defaults(handler=_bench_run)

    claims = bench_commands.add_parser("claims", help="run v2 on a claim-level dataset (gg-claims-v2 format)")
    claims.add_argument("--records", required=True, help="path to records.jsonl")
    claims.add_argument("--dataset-id", default="gg-claims-v2")
    claims.add_argument("--split", required=True, choices=("dev", "test", "all", "unreviewed"))
    claims.add_argument("--policy", help="builtin policy name or path to a .toml policy")
    claims.add_argument("--purpose", help="required for --split test; recorded in the test access log")
    claims.add_argument("--test-access-log", default="benchmark/results/TEST_ACCESS_LOG.jsonl")
    claims.add_argument("--calibration", help="calibration file from 'groundguard calibrate fit'")
    claims.add_argument("--out", help="write the run file to this path")
    claims.set_defaults(handler=_bench_claims)

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

    policy = commands.add_parser("policy", help="decision policies")
    policy_commands = policy.add_subparsers(dest="policy_command", required=True)
    check = policy_commands.add_parser("check", help="validate a policy and print its rules")
    check.add_argument("policy", help="builtin policy name or path to a .toml file")
    check.set_defaults(handler=_policy_check)
    listing = policy_commands.add_parser("list", help="list builtin policies")
    listing.set_defaults(handler=_policy_list)

    calibrate = commands.add_parser("calibrate", help="fit and evaluate confidence calibration")
    calibrate_commands = calibrate.add_subparsers(dest="calibrate_command", required=True)
    fit = calibrate_commands.add_parser("fit", help="fit calibrators on a dev-split claims run")
    fit.add_argument("--run", required=True, help="run file from 'groundguard bench claims' (not test)")
    fit.add_argument("--method", choices=("isotonic", "platt"), default="isotonic")
    fit.add_argument("--min-samples", type=int, default=30)
    fit.add_argument("--allow-unreviewed", action="store_true", help="development only")
    fit.add_argument("--out", required=True)
    fit.set_defaults(handler=_calibrate_fit)
    calibration_report_parser = calibrate_commands.add_parser("report", help="ECE and Brier score on a claims run")
    calibration_report_parser.add_argument("--run", required=True)
    calibration_report_parser.add_argument("--calibration", required=True)
    calibration_report_parser.set_defaults(handler=_calibrate_report)

    annotate = commands.add_parser("annotate", help="review claim-level dataset records")
    annotate_commands = annotate.add_subparsers(dest="annotate_command", required=True)
    review_parser = annotate_commands.add_parser("review", help="review NEEDS_REVIEW records interactively")
    review_parser.add_argument("records", help="path to a records.jsonl file")
    review_parser.add_argument("--reviewer", required=True, help="your reviewer id (a person, not 'ai-assistant')")
    review_parser.set_defaults(handler=_annotate_review)
    status_parser = annotate_commands.add_parser("status", help="summarize a records.jsonl file")
    status_parser.add_argument("records")
    status_parser.set_defaults(handler=_annotate_status)
    freeze_parser = annotate_commands.add_parser("freeze", help="freeze LABELED records into dev/test splits")
    freeze_parser.add_argument("records")
    freeze_parser.add_argument("--version", required=True)
    freeze_parser.set_defaults(handler=_annotate_freeze)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except (BenchmarkError, GroundGuardError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
