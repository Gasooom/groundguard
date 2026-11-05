"""Measure in-process latency and throughput of the v2 pipeline.

    python scripts/measure_latency.py --out benchmark/results/latency.<host>.json

Inputs: the 99 unique gg-legacy-v1 records (short contexts) and the same
answers against a long synthetic context (each record's context plus 40
filler sentences), so the effect of context length is visible. Numbers
depend on the machine; the hardware profile is recorded with them.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import time
from pathlib import Path

from groundguard.bench.datasets import deduplicate, load_legacy_v1
from groundguard.pipeline import evaluate_v2

FILLER = " ".join(f"Department {i} reviewed its quarterly maintenance schedule in detail." for i in range(40))


def _cpu_model() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unknown"


def _measure(cases, repeats: int) -> dict[str, float]:
    for question, context, answer in cases[:5]:  # warm-up
        evaluate_v2(question=question, context=context, answer=answer)
    timings = []
    start_all = time.perf_counter()
    for _ in range(repeats):
        for question, context, answer in cases:
            start = time.perf_counter()
            evaluate_v2(question=question, context=context, answer=answer)
            timings.append((time.perf_counter() - start) * 1000)
    elapsed = time.perf_counter() - start_all
    timings.sort()
    pick = lambda q: timings[min(len(timings) - 1, int(q * len(timings)))]
    return {
        "evaluations": len(timings),
        "p50_ms": round(pick(0.50), 3),
        "p95_ms": round(pick(0.95), 3),
        "p99_ms": round(pick(0.99), 3),
        "mean_ms": round(statistics.fmean(timings), 3),
        "throughput_per_second_single_process": round(len(timings) / elapsed, 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--out")
    args = parser.parse_args()

    records = deduplicate(load_legacy_v1().records)
    short = [(r.question, r.context, r.answer) for r in records]
    long = [(r.question, f"{r.context} {FILLER}", r.answer) for r in records]
    result = {
        "kind": "latency",
        "engine": "v2 default chain (guards, structured_facts, lexical), default policy, in-process",
        "hardware": {
            "cpu": _cpu_model(),
            "logical_cpus": os.cpu_count(),
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "inputs": {
            "short_context": f"{len(short)} unique gg-legacy-v1 records (median context 6 words)",
            "long_context": "same answers, context + 40 filler sentences (~360 words)",
            "repeats": args.repeats,
        },
        "short_context": _measure(short, args.repeats),
        "long_context": _measure(long, args.repeats),
        "caveat": "Single process, warm. Excludes HTTP, auth and storage. Optional NLI backend not measured.",
    }
    text = json.dumps(result, indent=2)
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
