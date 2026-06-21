# bench — proving the savings

The repo claims session-analyzer cuts token waste. This is where that claim is
measured, not estimated.

**Result: ~41% fewer tokens across 8 fixture tasks, task success unchanged**
(simple suite 50.9%, harder suite 26.8%). On a large, grep-friendly real repo a
*generic* CLAUDE.md did not help navigation — the savings live in exploration-
and re-read-heavy work, not cheap nav.

## Method (A/B, same task, two configs)

For each task in `tasks.jsonl`, the runner executes `claude -p` headlessly twice:

- **baseline** — a throwaway copy of `fixture/`, no project `CLAUDE.md`.
- **optimized** — the same copy plus `configs/optimized/CLAUDE.md`, the kind of
  orientation file the skill recommends generating (repo map, read-once rule, a
  single verify command).

The config is the only thing that differs, so the token delta is attributable to
it. Each run records real usage (`total_cost_usd`, input/output/cache tokens,
turns) from the `--output-format json` result, plus a **deterministic success
check** (`unittest` passes, or the answer contains the right file/identifier).

A saving only counts if the optimized arm's success rate is at least the
baseline's. Fewer tokens with a worse answer is not a saving.

## Run it

```bash
BENCH_MODEL=claude-sonnet-4-6 BENCH_REPEATS=2 python3 bench/run.py
python3 bench/report.py
```

Each task runs `REPEATS` times per arm to average out run-to-run nondeterminism;
the report shows per-task and overall savings with both success rates.

## Honest limits

- `claude -p` is nondeterministic; treat a single run as noise, the average of
  repeats as signal, and report the spread.
- This isolates the orientation-CLAUDE.md lever on a small fixture. It is a lower
  bound on a real, messy repo, and it does not capture the permission-allowlist
  or cross-session cache levers.
- The headline number names this suite and model. It is not a universal guarantee.
