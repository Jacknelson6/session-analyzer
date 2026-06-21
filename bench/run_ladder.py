#!/usr/bin/env python3
"""Difficulty-ladder A/B: Arm A (no gate) vs Arm C (verify gate) across tiers.

Finds the loop/output-quality cap: the tier where the gate's lift collapses.

Reads validated tasks from BENCH_TASKS_JSON (default bench/ladder-tasks.json):
  {"tasks": [{"tier","task_id","seed_files":[{path,content}],"hidden_test_content"}]}

For each (task, arm, rep): write only the seed into an isolated temp dir, run
`claude -p`, then AFTER the agent exits (anti-leakage) drop the hidden grader in
and run it. The gate (Arm C) never sees the hidden test; it acts on the agent's
own tests. Records tier/task/arm/rep/ok/tokens/turns to BENCH_RESULTS.

Env: BENCH_MODEL (default claude-sonnet-4-6), BENCH_REPEATS (default 3),
     BENCH_ARMS (default A,C), BENCH_RESULTS, BENCH_TASKS_JSON.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

BENCH = Path(__file__).resolve().parent
TASKS_JSON = Path(os.environ.get("BENCH_TASKS_JSON", BENCH / "ladder-tasks.json"))
GATE = BENCH / "configs" / "ladder-gate" / "CLAUDE.md"
RESULTS = Path(os.environ.get("BENCH_RESULTS", BENCH / "results-ladder.jsonl"))
MODEL = os.environ.get("BENCH_MODEL", "claude-sonnet-4-6")
REPEATS = int(os.environ.get("BENCH_REPEATS", "3"))
ARMS = [a.strip() for a in os.environ.get("BENCH_ARMS", "A,C").split(",") if a.strip()]

PROMPT = ("Read README.md in this directory and implement exactly what its goal and "
          "definition of done specify. Put your code at the path the README indicates.")


def _run(work: Path):
    r = subprocess.run(
        ["claude", "-p", PROMPT, "--output-format", "json",
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


def _grade(work: Path, hidden: str) -> bool:
    g = work / ".grade_hidden.py"
    g.write_text(hidden)
    rc = subprocess.run(["python3", ".grade_hidden.py"], cwd=str(work),
                        capture_output=True, text=True).returncode
    g.unlink(missing_ok=True)
    return rc == 0


def main() -> None:
    tasks = json.loads(TASKS_JSON.read_text())["tasks"]
    with RESULTS.open("w") as out:
        for task in tasks:
            for arm in ARMS:
                for rep in range(REPEATS):
                    tmp = Path(tempfile.mkdtemp(prefix="ladder_"))
                    work = tmp / "proj"
                    work.mkdir(parents=True)
                    for f in task["seed_files"]:
                        p = work / f["path"]
                        p.parent.mkdir(parents=True, exist_ok=True)
                        p.write_text(f["content"])
                    if arm == "C":
                        shutil.copy(GATE, work / "CLAUDE.md")
                    d = _run(work)
                    ok = _grade(work, task["hidden_test_content"]) if d else False
                    rec = {"tier": task["tier"], "task": task["task_id"], "arm": arm,
                           "rep": rep, "ok": ok,
                           "tokens": _tokens(d) if d else 0,
                           "turns": d.get("num_turns", 0) if d else 0}
                    out.write(json.dumps(rec) + "\n")
                    out.flush()
                    print(f"{task['tier']:3} {task['task_id']:24} {arm} rep{rep} ok={ok} tok={rec['tokens']}", flush=True)
                    shutil.rmtree(tmp, ignore_errors=True)
    print(f"\nwrote {RESULTS}", flush=True)


if __name__ == "__main__":
    main()
