<!--
Loop-design spec skeleton. Copy to workflows/<slug>.md and fill every section, or
mark a section "none (deliberate)" with a one-line reason. A spec is done when an
implementer agent could build AND run it with zero follow-up questions, and it
clears the low-cost / high-impact bar.
-->

# <workflow name>

**Goal:** one sentence -- what this loop produces and why it is worth running.

## Cost & impact (the bar)

- **Frequency:** how often a run fires (e.g. "every new PR", "daily 8am").
- **Toil / risk saved per run:** minutes reclaimed, errors caught, context-switch
  removed.
- **Estimated tokens per run:** rough number, with the main driver (e.g. "~6k:
  reads only the diff + orientation map, no full-repo scan").
- **Verdict:** why impact-per-token clears the bar (cheap-and-frequent), or what
  was changed to get it there.

## Trigger

Event or schedule, stated precisely. How it fires (webhook/poller/cron).

## Orient (cheap context)

The authoritative source of truth loaded first each run, so the worker does not
re-explore. In a code repo: the orientation map (`bin/analyze map`). Elsewhere:
the canonical doc / schema / list.

## Inputs

What each run consumes (sources, accounts, files), scoped to the minimum -- only
the new/changed items, not the whole corpus.

## Steps

1. ...
2. ...

## Encoded gate (programmatic)

The single command that returns pass/fail and proves a run is correct (tests,
build, lint, schema-validate, "does it parse/send"). If none exists yet, the first
step is to write it. This is the cheapest, highest-value gate.

## Judge (different model)

What needs judgement beyond the encoded check, the rubric, and the model family
used to judge it -- a **different family than the worker**, or a human. "None" is
valid if the encoded gate fully covers correctness.

## Verify-loop (surgical -- default OFF)

Only ON if this work genuinely fails first-pass or has missable implicit
requirements. If ON, name the **external localization signal** (failing
regression suite / different-model judge / human) the self-test loop relies on.
If OFF, say why (avoid the ~15-26% token tax on well-handled work).

## Checkpoint(s) & brief

Where a human decides, pushed as far right as allowed, and the decision-ready
brief they receive (what was produced, why, asset links). "None (deliberate)" is
a valid, deliberate answer -- say so.

## Output

The artifact each run produces, and where it lands.

## Definition of done (falsifiable)

Success criteria for a single run, stated so a script or judge could check them.

## On failure / uncertainty

What the loop does when a step fails or a result is low-confidence (retry, route
to a human, abort with a brief).

## Stop guards

- Max iterations (default 12)
- Revise cap per gate (default 3, then pass or escalate)
- No-progress / stall (stop after the same state twice)
- Budget cap (tokens or cost per run)

## Run context (Claude Code)

- **Invocation:** slash command / headless `claude -p ... --output-format json` /
  scheduled job.
- **Worker model:** the cheapest model that clears the bar (frontier only for the
  hard stage).
- **Judge model:** different family, run as a subagent.
- **Permissions:** the minimal tool/command allowlist for unattended runs.
- **State:** `state.json` (status/decisions/blockers/iteration) + `run-log.md`
  (timestamped stage outputs, gate verdicts, revisions).
