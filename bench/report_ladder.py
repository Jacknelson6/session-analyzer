#!/usr/bin/env python3
"""Aggregate the difficulty-ladder A/B and locate the cap.

Per tier: Arm A accuracy (first-pass, no gate) vs Arm C accuracy (verify gate),
the lift (delta), the paired incorrect->correct (rescues) and correct->incorrect
(damage) counts, and mean tokens. The cap is the lowest tier where the gate stops
helping: delta <= 0, or damage >= rescues.
"""

from __future__ import annotations

import json
import os
import statistics
from pathlib import Path

RESULTS = Path(os.environ.get("BENCH_RESULTS", Path(__file__).resolve().parent / "results-ladder.jsonl"))


def main() -> None:
    recs = [json.loads(l) for l in RESULTS.read_text().splitlines() if l.strip()]
    tiers = sorted({r["tier"] for r in recs})
    print(f"{'tier':5}{'A acc':>8}{'C acc':>8}{'lift':>8}{'i->c':>7}{'c->i':>7}{'A tok':>10}{'C tok':>10}")
    print("-" * 63)
    cap = None
    for t in tiers:
        A = [r for r in recs if r["tier"] == t and r["arm"] == "A"]
        C = [r for r in recs if r["tier"] == t and r["arm"] == "C"]
        if not A or not C:
            continue
        acc_a = sum(r["ok"] for r in A) / len(A)
        acc_c = sum(r["ok"] for r in C) / len(C)
        amap = {(r["task"], r["rep"]): r["ok"] for r in A}
        cmap = {(r["task"], r["rep"]): r["ok"] for r in C}
        keys = set(amap) & set(cmap)
        ic = sum(1 for k in keys if not amap[k] and cmap[k])
        ci = sum(1 for k in keys if amap[k] and not cmap[k])
        tok_a = statistics.mean(r["tokens"] for r in A)
        tok_c = statistics.mean(r["tokens"] for r in C)
        print(f"{t:5}{acc_a*100:7.0f}%{acc_c*100:7.0f}%{(acc_c-acc_a)*100:+7.0f}%{ic:>7}{ci:>7}{tok_a:10.0f}{tok_c:10.0f}")
        if cap is None and (acc_c - acc_a <= 0 or ci >= ic):
            cap = t
    print("-" * 63)
    print(f"\nCap tier (gate stops helping): {cap or 'not reached in tested tiers'}")


if __name__ == "__main__":
    main()
