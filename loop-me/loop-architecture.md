# The optimal loop architecture (for Claude Code and similar agents)

This is the architecture `loop-me` specs every loop against. It is not a
preference; the trade-offs below were measured in this repo's benchmark
(`bench/`, `docs/loop-cap.md`). Keep this file next to `SKILL.md` so the skill is
self-contained when copied to `~/.claude/skills/loop-me/`.

## The shape

```
Trigger (event or schedule)
  -> Orient        load the orientation map (authoritative file/symbol index)
  -> Plan          draft plan.md
  -> Plan gate     judge model (different family); revise <= 3, else stop
  -> Execute       the workflow stages
  -> Delivery gate encoded programmatic check AND a different-model judge; revise <= 3
  -> Checkpoint    a decision-ready brief to the human, pushed as far right as allowed (if any)
  -> Done          all gates pass and the definition of done is met
state.json (status/decisions/blockers/iteration) + run-log.md (timestamped) run alongside.
```

## The four rules, with the numbers

1. **Orientation map first -- the default token lever.**
   Giving the worker an authoritative index of the files/symbols it touches,
   instead of letting it re-explore each run, is a Pareto win:

   | model | tokens | accuracy |
   | --- | --- | --- |
   | Opus 4.8 | **-17%** | 89% -> **100%** |
   | Sonnet 4.6 | flat (+2%) | 67% -> **78%** |

   Across an 8-task suite it saved ~41% (Sonnet) to ~47% (Opus) tokens with task
   success held. In a code repo the orient step is `bin/analyze map`; elsewhere it
   is the canonical doc / schema / source-of-truth list.

2. **Encode the one check the agent cannot infer.**
   The highest-value gate is a command that returns pass/fail: the test, the
   build, the lint, the schema validation, "does the output parse/send." This is
   what lets the loop close itself instead of handing back to a human. Push
   hardest for this; if it does not exist yet, writing it is usually step one.

3. **The judge is a different model than the worker.**
   The model that did the work must not be the only one grading it. Spec the judge
   as a subagent on a different model family, or a human checkpoint. Never silent
   self-approval.

4. **Add a verify-loop surgically, not by default.**
   A blanket "write and run your own edge-case tests before finishing" gate is
   *dominated*:

   | arm | first-pass | gate result | token cost |
   | --- | --- | --- | --- |
   | Opus 4.8 | 100% (24/24) | 100%, 0 rescued / 0 broke | +15% |
   | Sonnet 4.6 | 92% (22/24) | 96%, 2 rescued / 1 broke | +15% |

   On work the model already one-shots, the gate is pure token overhead and can
   churn (break as often as it rescues). It earns its tokens only where
   requirements are genuinely implicit AND missable -- there the same gate took
   Sonnet from 50-67% to 100%. For "symptom far from cause" localization bugs, a
   blind self-test loop hits a wall and needs an **external localization signal**:
   a failing regression suite, a different-model judge, or a human.

## Gates verify three ways

- **Programmatic** -- a command returns pass/fail. The check Claude can encode.
- **Judge** -- a model scores a rubric (different family than the worker).
- **Human** -- a person signs off at a checkpoint.

## Stop guards (a loop is never emitted without all of them)

- A falsifiable success criterion, defined up front.
- Max iterations (default 12).
- A revise cap per gate (default 3, then pass or escalate).
- A no-progress / stall signal (stop after the same state twice).
- A budget cap (tokens or cost per run).

## Running it as a Claude Code loop

- **Invocation:** an in-session slash command, a headless
  `claude -p "<prompt>" --output-format json` run, or a scheduled job that calls
  the headless command.
- **Triggers:** events via a webhook/poller that runs the headless command;
  schedules via cron or the host scheduler.
- **Judge:** a subagent pinned to a different model family.
- **Permissions:** a minimal settings allowlist of the exact tools/commands the
  loop needs, so it runs unattended without prompts.
- **Context:** the orient step loads the orientation map so each run starts
  pre-navigated.

For a runnable, compiled spec (loop.yaml -> loop.resolved.json + a runner), hand
the finished workflow spec to the `looper` skill (`/looper`).
