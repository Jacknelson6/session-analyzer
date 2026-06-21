# Loop architecture

When session-analyzer finds a loop that should run autonomously, it recommends
structuring it the way [looper](https://github.com/ksimback/looper) does. Looper
is the baseline architecture for every loop improvement this tool suggests.

## The shape

```
Goal + context (process notes + definition of done)
   -> draft plan.md (the host model)
   -> Plan gate        (judge = a reviewer model; revise <= 3, else pass)
   -> write delivery-N.md (map the workflow)
   -> Delivery gate    (programmatic check + judge; revise <= 3, else pass)
   -> Final output (all gates clean)
```

State and log run alongside the whole thing:
- `state.json` records status, decisions, blockers, and the current iteration.
- `run-log.md` is a timestamped log of stage outputs, gate verdicts, and revisions.

## Files a loop owns

- `loop.yaml` is the spec: goal, stages, gates, verification, control params.
- `loop.resolved.json` is the compiled, ready-to-run spec.
- `run-loop.py` is a runner you own and edit; it runs the loop outside the session.
- `RUN_IN_SESSION.md` is a handoff prompt to run the loop in the current session.
- `state.json` and `run-log.md` track execution (above).

## Gates verify three ways

- **Programmatic**: a command returns pass/fail. This is the check Claude can
  encode, and the one session-analyzer pushes hardest for.
- **Judge**: a model scores a rubric.
- **Human**: you sign off.

Default the judge to a *different model family than the host*, so the model that
did the work is not the one grading it. A local model (e.g. Ollama) keeps the
council in-house.

## Stop guards (a loop is never emitted without one)

- A falsifiable success criterion, defined up front.
- Max iterations (looper default: 12).
- A revise cap per gate (default: 3).
- A no-progress signal (stall x2).
- A budget cap (tokens or cost).

## What session-analyzer adds

It reads your sessions and finds where a loop ran without this structure: no
definition of done, no gate, retry loops, hand-backs to you. Then it emits the
missing pieces in this shape, the definition of done, the plan and delivery
gates, the programmatic check, and the stop guards. For a full, runnable spec it
points you at the `looper` skill (`/looper`).
