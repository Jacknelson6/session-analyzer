# SA-Bench

The **Session Analyzer Benchmark**: a from-scratch A/B harness that measures
whether a Claude Code workflow change actually pays. The same tasks run with vs
without the change under `claude -p`, with real token usage and blind hidden-test
grading (the grader is added only after the agent exits). This is where the repo's
claims are measured, not estimated.

## Headline results

Orientation map, 3-arm run on a 23-file repo with multi-step feature tasks
(pass rate / mean tokens):

| config | Sonnet 4.6 | Opus 4.8 |
| --- | --- | --- |
| no map | 67% / 515K | 89% / 1.08M |
| **+ orientation map** | **78% / 524K** | **100% / 889K** |
| + verify gate | 78% / 649K | 100% / 1.27M |

- **Orientation map = Pareto win:** Opus -17% tokens and 89 -> 100% pass; Sonnet
  better output at flat cost. Across a separate 8-task suite it saves ~41%
  (Sonnet) to ~47% (Opus) tokens with output held at 100%.
- **Verify gate = dominated:** matches the map's accuracy for +18-26% tokens, no
  gain. Surgical, not a default.
- **Loop cap** (difficulty ladder): the gate only helps in the narrow band where
  the model fails first-pass and has a real check. See `../docs/loop-cap.md`.

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

### Proving the *generated* map (the `map` command)

The optimized arm above used a hand-written `configs/optimized/CLAUDE.md`. The
`map` command now generates that artifact deterministically. To prove the
generated map is a drop-in for the validated one, point the runner at it:

```bash
./bin/analyze map --repo bench/fixture --out /tmp/generated-map.md
BENCH_OPT_CLAUDE=/tmp/generated-map.md python3 bench/run.py
python3 bench/report.py
```

A zero-token structural proof runs in the test suite
(`OrientationMap.test_matches_validated_winning_config`): it asserts the
generated map carries the same module index, public surface, and verify command
as the benchmark-validated config, so the measured savings transfer.

Each task runs `REPEATS` times per arm to average out run-to-run nondeterminism;
the report shows per-task and overall savings with both success rates.

## Honest limits

- `claude -p` is nondeterministic; treat a single run as noise, the average of
  repeats as signal, and report the spread.
- This isolates the orientation-CLAUDE.md lever on a small fixture. It is a lower
  bound on a real, messy repo, and it does not capture the permission-allowlist
  or cross-session cache levers.
- The headline number names this suite and model. It is not a universal guarantee.
