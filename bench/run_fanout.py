#!/usr/bin/env python3
"""Cycle 1 of the RSI loop: does fan-out (context isolation) beat a monolithic
session on tokens and first-pass correctness?

Arm A (monolithic): one `claude -p` adds ALL features in a single session, so
context accumulates across the whole task.
Arm B (fan-out): one fresh `claude -p` per feature on the same work dir, so each
sub-session carries only its own tiny context.

Both use the verify-gate config. Success = every feature passes .verify/check.py.
Reports total tokens and turns per arm so we can see the tradeoff honestly.

Env: BENCH_MODEL (default claude-sonnet-4-6), BENCH_REPEATS (default 2),
     BENCH_RESULTS (default bench/results-fanout.jsonl)
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

BENCH = Path(__file__).resolve().parent
FIXTURE = BENCH / "fixture"
GATE = BENCH / "configs" / "verify-gate" / "CLAUDE.md"
RESULTS = Path(os.environ.get("BENCH_RESULTS", BENCH / "results-fanout.jsonl"))
MODEL = os.environ.get("BENCH_MODEL", "claude-sonnet-4-6")
REPEATS = int(os.environ.get("BENCH_REPEATS", "2"))

FEATURES = [
    "apply_discount(amount, pct) that returns amount reduced by pct percent (e.g. apply_discount(100, 10) == 90)",
    "average_amount(store) that returns the mean of all transaction amounts",
    "format_total(amount) that returns a price string, e.g. format_total(12.5) == '$12.50'",
    "total_for_account(store, account_id) that returns the summed amounts for that account",
    "max_transaction(store) that returns the largest transaction amount",
]


def _run(prompt: str, work: Path):
    r = subprocess.run(
        ["claude", "-p", prompt, "--output-format", "json",
         "--dangerously-skip-permissions", "--model", MODEL],
        cwd=str(work), capture_output=True, text=True,
    )
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def _tokens(d: dict) -> int:
    u = d.get("usage", {})
    return (u.get("input_tokens", 0) + u.get("output_tokens", 0)
            + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0))


def _fresh():
    tmp = Path(tempfile.mkdtemp(prefix="fanout_"))
    work = tmp / "proj"
    shutil.copytree(FIXTURE, work)
    shutil.copy(GATE, work / "CLAUDE.md")
    return tmp, work


def _check(work: Path) -> bool:
    return subprocess.run(["python3", ".verify/check.py"], cwd=str(work),
                          capture_output=True, text=True).returncode == 0


def main() -> None:
    with RESULTS.open("w") as out:
        for rep in range(REPEATS):
            # Arm A: monolithic, one session for all features
            tmp, work = _fresh()
            prompt = "Add these functions to ledger/report.py: " + "; ".join(FEATURES) + "."
            d = _run(prompt, work)
            rec = {"arm": "monolithic", "rep": rep,
                   "tokens": _tokens(d) if d else 0,
                   "turns": d.get("num_turns", 0) if d else 0,
                   "ok": _check(work) if d else False}
            out.write(json.dumps(rec) + "\n"); out.flush()
            print(f"monolithic rep{rep} tok={rec['tokens']} turns={rec['turns']} ok={rec['ok']}", flush=True)
            shutil.rmtree(tmp, ignore_errors=True)

            # Arm B: fan-out, one fresh session per feature on the same work dir
            tmp, work = _fresh()
            tok = turns = 0
            for feat in FEATURES:
                d = _run(f"Add a function {feat} to ledger/report.py.", work)
                if d:
                    tok += _tokens(d)
                    turns += d.get("num_turns", 0)
            rec = {"arm": "fanout", "rep": rep, "tokens": tok, "turns": turns, "ok": _check(work)}
            out.write(json.dumps(rec) + "\n"); out.flush()
            print(f"fanout     rep{rep} tok={rec['tokens']} turns={rec['turns']} ok={rec['ok']}", flush=True)
            shutil.rmtree(tmp, ignore_errors=True)
    print(f"\nwrote {RESULTS}", flush=True)


if __name__ == "__main__":
    main()
