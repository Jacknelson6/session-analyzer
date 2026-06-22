#!/usr/bin/env python3
"""3-arm Pareto demo: baseline vs orientation-map vs verify-gate, on a multi-step
feature task in a medium interconnected repo. Measures tokens at EQUAL output
(hidden-test pass) to show that the orientation map cuts tokens with output held,
while the verify gate adds them.

Input BENCH_PARETO_JSON (default bench/pareto.json):
  {"repo_seed_files":[{path,content}], "orientation_md":"...",
   "tasks":[{task_id, task_md, hidden_test_content}]}

Arms: baseline (no CLAUDE.md), orient (orientation_md as CLAUDE.md),
      gate (the ladder-gate CLAUDE.md). The hidden grader is added only after the
      agent exits. Env: BENCH_MODEL, BENCH_REPEATS (3), BENCH_RESULTS, BENCH_ARMS.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

BENCH = Path(__file__).resolve().parent
PARETO = Path(os.environ.get("BENCH_PARETO_JSON", BENCH / "pareto.json"))
GATE_MD = (BENCH / "configs" / "ladder-gate" / "CLAUDE.md").read_text()
RESULTS = Path(os.environ.get("BENCH_RESULTS", BENCH / "results-pareto.jsonl"))
MODEL = os.environ.get("BENCH_MODEL", "claude-sonnet-4-6")
REPEATS = int(os.environ.get("BENCH_REPEATS", "3"))
ARMS = [a.strip() for a in os.environ.get("BENCH_ARMS", "baseline,orient,gate").split(",") if a.strip()]

PROMPT = ("Read TASK.md in this directory and implement the feature it specifies in this "
          "codebase. Put the changes in the appropriate existing files.")


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
    (work / ".grade_hidden.py").write_text(hidden)
    rc = subprocess.run(["python3", ".grade_hidden.py"], cwd=str(work),
                        capture_output=True, text=True).returncode
    (work / ".grade_hidden.py").unlink(missing_ok=True)
    return rc == 0


def main() -> None:
    spec = json.loads(PARETO.read_text())
    seed, orient_md = spec["repo_seed_files"], spec["orientation_md"]
    with RESULTS.open("w") as out:
        for task in spec["tasks"]:
            for arm in ARMS:
                for rep in range(REPEATS):
                    tmp = Path(tempfile.mkdtemp(prefix="pareto_"))
                    work = tmp / "proj"
                    work.mkdir(parents=True)
                    for f in seed:
                        p = work / f["path"]
                        p.parent.mkdir(parents=True, exist_ok=True)
                        p.write_text(f["content"])
                    (work / "TASK.md").write_text(task["task_md"])
                    if arm == "orient":
                        (work / "CLAUDE.md").write_text(orient_md)
                    elif arm == "gate":
                        (work / "CLAUDE.md").write_text(GATE_MD)
                    d = _run(work)
                    ok = _grade(work, task["hidden_test_content"]) if d else False
                    rec = {"task": task["task_id"], "arm": arm, "rep": rep, "ok": ok,
                           "tokens": _tokens(d) if d else 0,
                           "turns": d.get("num_turns", 0) if d else 0}
                    out.write(json.dumps(rec) + "\n")
                    out.flush()
                    print(f"{task['task_id']:26} {arm:9} rep{rep} ok={ok} tok={rec['tokens']}", flush=True)
                    shutil.rmtree(tmp, ignore_errors=True)
    print(f"\nwrote {RESULTS}", flush=True)


if __name__ == "__main__":
    main()
