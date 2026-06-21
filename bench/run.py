#!/usr/bin/env python3
"""A/B benchmark runner for session-analyzer.

For each task, runs `claude -p` headlessly under two configs (baseline = no
project CLAUDE.md; optimized = the skill-tuned orientation CLAUDE.md), on a fresh
throwaway copy of the fixture, capturing real token usage and a deterministic
success check. The only thing that differs between the two arms is the config,
so the token delta is attributable to it.

Env:
  BENCH_MODEL    model id (default claude-sonnet-4-6)
  BENCH_REPEATS  runs per (task, config) to average out nondeterminism (default 2)
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

BENCH = Path(__file__).resolve().parent
FIXTURE = Path(os.environ.get("BENCH_FIXTURE", BENCH / "fixture"))
TASKS = Path(os.environ.get("BENCH_TASKS", BENCH / "tasks.jsonl"))
OPT_CLAUDE = Path(os.environ.get("BENCH_OPT_CLAUDE", BENCH / "configs" / "optimized" / "CLAUDE.md"))
RESULTS = Path(os.environ.get("BENCH_RESULTS", BENCH / "results.jsonl"))
MODEL = os.environ.get("BENCH_MODEL", "claude-sonnet-4-6")
REPEATS = int(os.environ.get("BENCH_REPEATS", "2"))
IGNORE = shutil.ignore_patterns("node_modules", ".git", ".next", "dist", "build",
                                ".turbo", "coverage", ".venv", "__pycache__", ".cache")


def run_one(prompt: str, workdir: Path):
    cmd = ["claude", "-p", prompt, "--output-format", "json",
           "--dangerously-skip-permissions", "--model", MODEL]
    r = subprocess.run(cmd, cwd=str(workdir), capture_output=True, text=True)
    try:
        return json.loads(r.stdout), None
    except json.JSONDecodeError:
        return None, (r.stdout[-400:] + " | " + r.stderr[-400:]).strip()


def main() -> None:
    tasks = [json.loads(l) for l in TASKS.read_text().splitlines() if l.strip()]
    only = os.environ.get("BENCH_ONLY")
    if only:
        keep = {x.strip() for x in only.split(",")}
        tasks = [t for t in tasks if t["id"] in keep]
    with RESULTS.open("w") as out:
        for task in tasks:
            for config in ("baseline", "optimized"):
                for rep in range(REPEATS):
                    tmp = Path(tempfile.mkdtemp(prefix="bench_"))
                    work = tmp / "proj"
                    shutil.copytree(FIXTURE, work, ignore=IGNORE)
                    if config == "optimized":
                        shutil.copy(OPT_CLAUDE, work / "CLAUDE.md")
                    else:
                        (work / "CLAUDE.md").unlink(missing_ok=True)
                    if task.get("setup"):
                        subprocess.run(task["setup"], shell=True, cwd=str(work))

                    data, err = run_one(task["prompt"], work)
                    if data is None:
                        rec = {"task": task["id"], "config": config, "rep": rep, "error": err}
                    else:
                        (work / ".bench_result.txt").write_text(data.get("result", ""))
                        ok = subprocess.run(task["check"], shell=True, cwd=str(work),
                                            capture_output=True, text=True).returncode == 0
                        u = data.get("usage", {})
                        total = (u.get("input_tokens", 0) + u.get("output_tokens", 0)
                                 + u.get("cache_read_input_tokens", 0)
                                 + u.get("cache_creation_input_tokens", 0))
                        rec = {"task": task["id"], "config": config, "rep": rep,
                               "input_tokens": u.get("input_tokens", 0),
                               "output_tokens": u.get("output_tokens", 0),
                               "cache_read": u.get("cache_read_input_tokens", 0),
                               "cache_creation": u.get("cache_creation_input_tokens", 0),
                               "total_tokens": total,
                               "cost_usd": data.get("total_cost_usd", 0.0),
                               "num_turns": data.get("num_turns", 0),
                               "success": ok,
                               "answer": data.get("result", "")[:500]}
                    out.write(json.dumps(rec) + "\n")
                    out.flush()
                    tag = rec.get("error", f"tok={rec.get('total_tokens')} ${rec.get('cost_usd', 0):.3f} turns={rec.get('num_turns')} ok={rec.get('success')}")
                    print(f"{task['id']:14} {config:9} rep{rep}  {tag}", flush=True)
                    shutil.rmtree(tmp, ignore_errors=True)
    print(f"\nwrote {RESULTS}", flush=True)


if __name__ == "__main__":
    main()
