#!/usr/bin/env python3
"""Aggregate the 3-arm Pareto demo: accuracy + mean tokens per arm.

The point: orientation should be cheaper than baseline at the same accuracy
(tokens down, output held), and the gate should be more expensive.
"""

from __future__ import annotations

import json
import os
import statistics
from pathlib import Path

RESULTS = Path(os.environ.get("BENCH_RESULTS", Path(__file__).resolve().parent / "results-pareto.jsonl"))


def main() -> None:
    recs = [json.loads(l) for l in RESULTS.read_text().splitlines() if l.strip()]
    print(f"{'arm':10}{'accuracy':>10}{'mean tok':>11}{'vs baseline':>13}")
    print("-" * 44)
    base = None
    for arm in ["baseline", "orient", "gate"]:
        xs = [r for r in recs if r["arm"] == arm]
        if not xs:
            continue
        acc = sum(r["ok"] for r in xs) / len(xs)
        tok = statistics.mean(r["tokens"] for r in xs)
        if arm == "baseline":
            base = tok
        delta = f"{(tok-base)/base*100:+.0f}%" if base else "n/a"
        print(f"{arm:10}{acc*100:9.0f}%{tok:11.0f}{delta:>13}")
    print("-" * 44)
    print("\nGoal: orient < baseline tokens at equal accuracy; gate > baseline.")


if __name__ == "__main__":
    main()
