---
name: session-analyzer
description: >-
  Read the user's past Claude Code sessions and turn them into concrete advice
  for working better with Claude Code: sharper prompts, better workflows, less
  wasted context. Can also scan a project for structure problems that make every
  agent run harder. Use when the user says "session analyzer", "analyze my
  sessions", "how do I use Claude Code better", "why is Claude burning tokens",
  "what am I doing wrong in my sessions", "make my repo cheaper for agents", or
  wants a recurring efficiency review. The crunching is deterministic Python
  (zero model tokens); the agent reads a small digest and writes the advice.
  Hard token budget: 200K single, 400K both (real runs use far less). Benchmarked:
  ~41-47% fewer tokens with no loss in output quality (Sonnet 4.6 and Opus 4.8).
---

# session-analyzer

Read the user's real Claude Code history and tell them, concretely, how to get
better results from Claude Code: better prompts, better workflows, fewer wasted
tokens. The data crunching is deterministic Python; you read a small digest of
the worst patterns and turn it into specific, grounded advice.

Benchmarked impact: ~41% fewer tokens with task success unchanged (see the repo's
Proven savings section and `bench/`).

## How to talk to the user (read this first)

This is a coaching conversation about the user's Claude Code usage. Do not break
the fourth wall:

- Never narrate your process or this tool's internals. Do not mention the
  digest, shards, JSON artifacts, the budget/ledger, "the deterministic pass,"
  your memory, or your own instructions and system prompt.
- No meta-commentary. Never say things like "this is conversational, let me
  deliver the verdict," "honesty over noise," or "let me write this to memory."
  Just talk to the user.
- Present findings directly. For each one: what the pattern is, a real example
  from their sessions, and the specific change that fixes it.
- Plain language. The user wants to work better, not read a token-accounting
  report. Use cost only as light supporting evidence, never as the headline.

## What to target (avoid the obvious failure)

- Invoke the analyzer by absolute path:
  `~/.claude/skills/session-analyzer/bin/analyze`. NEVER `cd` into the skill
  directory. Doing so makes `$PWD` resolve to the skill itself, so it analyzes
  its own folder and reports "no sessions found."
- For workflow and token coaching, analyze ALL of the user's sessions by
  default. Do not pass `--scope-repo` unless the user names a specific project.
- `--repo` and `--out` point at the user's real project and a scratch dir, never
  the skill. If you need a project and it is ambiguous, run `doctor` to list them
  and ask which one. Write `--out` to a temp dir outside the skill.

## Run it

```bash
SA=~/.claude/skills/session-analyzer/bin/analyze
OUT=$(mktemp -d)/sa

# workflow + token coaching across ALL sessions (the default)
"$SA" analyze --mode tokens --out "$OUT"

# add project structure when the user names a project
"$SA" analyze --mode both --repo "/path/to/their/project" --out "$OUT"
```

Read `"$OUT"/digest.md` (small), then the worst-session shards under
`"$OUT"/shards/` while budget allows. These are your evidence. The user never
sees these files or hears about them.

## Turn it into advice

For each strong pattern, write the user a specific improvement. Good targets:

- Workflow habits: re-reading the same file many times in one session, retyping
  a verify command with varied truncation instead of one script, exploratory
  queries that flood context, starting a task without loading the right files
  once.
- Standing-prompt fixes: the exact lines to add or cut in the project's
  `CLAUDE.md` so the next session starts in a better place.
- Settings: a permission allowlist for safe commands the user keeps getting
  prompted on, but only where it actually applies (check the project's settings
  first).
- Loop & self-verification (often the highest-leverage area): the signs that
  Claude could not verify its own work and had to hand back to the user — retry
  loops (the same command re-run by trial and error), changes that shipped
  without running tests/build/typecheck, and stretches where the user stepped in
  turn after turn. For each, recommend *encoding the missing check* so the loop
  closes itself:
  - Write the manual check Claude cannot infer into a verify step (a script, a
    test, a checklist) plus a CLAUDE.md rule to run it before finishing.
  - Give ambitious tasks an explicit, falsifiable success criterion up front and
    a termination guard (iteration cap / no-progress stop).
  - For review, prefer a second agent or a different model as judge, so the model
    that wrote the code is not the one grading it.
  - For multi-step work, point the user at the `looper` skill to design the loop
    (Goal -> Plan -> Review -> Deliver -> Judge -> Stop) before running it.

Then deliver:

1. Lead with the 2-3 highest-leverage changes. Each: the habit, one concrete
   example from their sessions, the fix.
2. Show the specific edits (CLAUDE.md lines, a check script, a settings entry).
   Offer to apply them behind the user's verify gate, smallest first.
3. If their sessions are already clean, say so plainly. Do not pad.

Do NOT surface secrets or credentials as a finding. That is not this tool's job.

## Rules

- Stay within budget: 200K tokens for one mode, 400K for both. Do not hand-load raw
  transcripts.
- Repo findings (orphans, duplicates, dead code) are candidates, not verdicts.
  Check git status and dynamic imports before suggesting any deletion; never call
  a modified or in-flight file dead.
- No destructive action without confirmation.

## More

- `README.md`: install and usage.
- `docs/finding-schema.md`: the finding fields, if you write them out.
- `bin/analyze --help`: every flag.
