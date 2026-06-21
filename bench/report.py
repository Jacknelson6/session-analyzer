#!/usr/bin/env python3
"""Aggregate bench/results.jsonl into a savings table.

Reports mean tokens per (task, config), the savings % (baseline -> optimized),
and the success rate of each arm. A savings number only counts if the optimized
arm's success rate is >= the baseline arm's: tokens saved at the cost of a wrong
answer is not a saving.
"""

from __future__ import annotations

import json
import os
import statistics
from pathlib import Path

RESULTS = Path(os.environ.get("BENCH_RESULTS", Path(__file__).resolve().parent / "results.jsonl"))


def main() -> None:
    recs = [json.loads(l) for l in RESULTS.read_text().splitlines() if l.strip()]
    ok = [r for r in recs if "error" not in r]
    errs = [r for r in recs if "error" in r]
    by = {}
    for r in ok:
        by.setdefault((r["task"], r["config"]), []).append(r)

    print(f"{'task':14} {'base tok':>9} {'opt tok':>9} {'save%':>7} {'base ok':>8} {'opt ok':>7}")
    print("-" * 60)
    tot_b = tot_o = 0.0
    quality_ok = True
    for task in sorted({t for t, _ in by}):
        b, o = by.get((task, "baseline")), by.get((task, "optimized"))
        if not b or not o:
            continue
        bt = statistics.mean(x["total_tokens"] for x in b)
        ot = statistics.mean(x["total_tokens"] for x in o)
        tot_b += bt
        tot_o += ot
        save = 100 * (bt - ot) / bt if bt else 0.0
        bok = sum(x["success"] for x in b) / len(b)
        ook = sum(x["success"] for x in o) / len(o)
        if ook < bok:
            quality_ok = False
        print(f"{task:14} {bt:>9.0f} {ot:>9.0f} {save:>6.1f}% {bok:>7.0%} {ook:>6.0%}")

    print("-" * 60)
    if tot_b:
        overall = 100 * (tot_b - tot_o) / tot_b
        print(f"{'OVERALL':14} {tot_b:>9.0f} {tot_o:>9.0f} {overall:>6.1f}%")
        verdict = "quality held" if quality_ok else "WARNING: optimized lost quality on >=1 task"
        print(f"\nToken savings: {overall:.1f}%  ({verdict})")
    if errs:
        print(f"\n{len(errs)} runs errored (excluded). First: {errs[0].get('error','')[:200]}")


if __name__ == "__main__":
    main()
