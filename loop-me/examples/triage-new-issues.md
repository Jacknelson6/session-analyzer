<!--
Worked example produced by loop-me. Note how the spec is shaped to be cheap
(orientation map, diff-scoped reads, encoded gate, no blanket verify-loop, cheap
worker model) and the cost/impact bar is stated explicitly.
-->

# Triage new GitHub issues

**Goal:** label, prioritize, and route every new issue within minutes of it
opening, so the maintainer reviews a clean, decision-ready queue instead of raw
issues.

## Cost & impact (the bar)

- **Frequency:** ~40 new issues/week (every `issues.opened` event).
- **Toil / risk saved per run:** ~3 min of maintainer triage per issue, and
  consistent labeling the maintainer kept getting wrong under load.
- **Estimated tokens per run:** ~4k -- reads the one issue body + the repo's label
  list + the orientation map; no full-repo or full-history scan.
- **Verdict:** high-frequency, cheap per run, removes a daily context-switch.
  Clears the bar easily (cheap-and-frequent). A "weekly backlog re-triage" variant
  was rejected: rare and would re-read every open issue (expensive per run).

## Trigger

Event: GitHub `issues.opened` webhook -> runs the headless command.

## Orient (cheap context)

Load the orientation map for the repo (`bin/analyze map`) plus the canonical label
taxonomy from `.github/labels.yml`. Both are small and stable, so they cache.

## Inputs

Only the new issue's title + body + author, and the label list. No other issues.

## Steps

1. Classify the issue: bug / feature / question / docs / duplicate.
2. Assign labels from the taxonomy and a priority (P0-P3) from a rubric.
3. If it looks like a duplicate, link the candidate original.
4. Post the labels + a one-line triage note; route P0/P1 to the on-call.

## Encoded gate (programmatic)

A validator script asserts: every assigned label exists in `.github/labels.yml`,
exactly one priority is set, and the output JSON matches the schema. Returns
pass/fail. Cheap, deterministic, catches the only failure that matters (invalid
labels/priority).

## Judge (different model)

For duplicate-linking only (the judgement-heavy step), a subagent on a different
model family confirms the linked issue is actually a duplicate before posting.
Classification/labeling needs no judge -- the encoded gate covers it.

## Verify-loop (surgical -- default OFF)

OFF. Labeling from a fixed taxonomy is well-handled first-pass; a self-test loop
would add tokens and churn for no gain. (If audit later shows mislabels, turn it
on for the classify step only.)

## Checkpoint(s) & brief

None for P2/P3 (posted automatically). For P0/P1, push-right to a single
checkpoint: a brief to the on-call -- title, why it is P0/P1, suspected area from
the orientation map, and a link -- so they decide in one glance.

## Output

Labels + priority + triage note on the issue; a routed brief for P0/P1.

## Definition of done (falsifiable)

Issue has >=1 valid label, exactly one priority, a triage note posted, and (if
duplicate) a linked original -- all within 5 minutes of opening.

## On failure / uncertainty

If classification confidence is low, apply `needs-triage` and route to the human
with the brief rather than guessing. If the gate fails, do not post; retry once,
then escalate.

## Stop guards

- Max iterations: 3 (label -> gate -> revise; this is a short loop).
- Revise cap per gate: 2.
- No-progress: stop if the gate fails the same way twice.
- Budget cap: 15k tokens/run (hard stop; normal run ~4k).

## Run context (Claude Code)

- **Invocation:** headless `claude -p "<triage prompt>" --output-format json`,
  fired by the webhook.
- **Worker model:** Haiku-tier (classification from a fixed taxonomy is easy);
  frontier model not needed.
- **Judge model:** a different family, subagent, duplicate-check only.
- **Permissions:** allowlist the GitHub label/comment tools and the validator
  script; nothing else.
- **State:** `state.json` + `run-log.md` per run for audit.
