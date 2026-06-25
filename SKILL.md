---
name: session-analyzer
description: >-
  Read the user's past Claude Code sessions and turn them into concrete advice
  for working better with Claude Code: sharper prompts, better workflows, less
  wasted context. Can also scan a project for structure problems that make every
  agent run harder. Use when the user says "session analyzer", "analyze my
  sessions", "how do I use Claude Code better", "why is Claude burning tokens",
  "what am I doing wrong in my sessions", "make my repo cheaper for agents",
  "give this repo an orientation map", or wants a recurring efficiency review. It
  can generate an orientation CLAUDE.md (the benchmark-proven token lever) on
  demand, and it can design a recurring task into a low-cost, high-impact agent
  loop when the user says "loop me", "what should I automate", "find work I can
  hand to AI", or "design a workflow". The crunching is deterministic Python
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

## Decide what to run (routing)

One entry point; you pick the path from what the user said. Read the request, then:

- **Default — token + loop coaching.** Any general ask ("session analyzer", "why
  is Claude burning tokens", "what am I doing wrong") → analyze ALL sessions for
  token waste and loop gaps. This always runs unless the user clearly wants only
  one of the below.
- **Add a repo scan** when the user names or points at a project, or asks about
  repo structure / cleanliness / "make my repo cheaper for agents" → run the repo
  scan too (token + repo, ranked together). If which project is ambiguous, run
  `doctor` and ask.
- **Generate the orientation map** when the user asks to "map this repo", OR when
  the session analysis shows repeated tree re-exploration (re-reads, broad
  searches before editing) in a known project → generate it and offer it. The map
  is the highest-leverage token lever, so reach for it whenever re-exploration is
  the pattern.
- **Switch to loop design** when the user wants to delegate a recurring task
  ("loop me", "what should I automate", "find work I can hand to AI", "design a
  workflow") → follow the loop-design section below. This is the one path that
  needs an explicit intent; do not start an interview unprompted.

These are not exclusive: a single request can run the session analysis, surface
the map as the top fix, and end by offering to design a loop. Default to doing the
analysis first — it is the evidence the other paths build on.

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
- The orientation map (the highest-leverage, benchmark-proven token lever:
  ~41-47% fewer tokens with output quality held). When a project keeps making
  Claude re-explore the tree, generate one instead of hand-writing it:
  `"$SA" map --repo "/path/to/project" --out "/path/to/project/CLAUDE.md"`.
  It emits an authoritative file/symbol index plus a read-once rule and a single
  detected verify command. Review it, then offer it to the user behind their
  verify gate.
- Settings: a permission allowlist for safe commands the user keeps getting
  prompted on, but only where it actually applies (check the project's settings
  first).
- Loop & self-verification (often the highest-leverage area). Look for signs that
  Claude could not verify its own work and had to hand back to the user: retry
  loops (the same command re-run by trial and error), changes that shipped without
  running tests/build/typecheck, and stretches where the user stepped in turn
  after turn. Recommend the looper loop architecture (see
  `docs/loop-architecture.md`) so the loop closes itself:
  - Define the goal and a falsifiable definition of done up front.
  - Encode the manual check Claude cannot infer as a programmatic gate (a script
    or test), classified programmatic / judge / human, plus a CLAUDE.md rule to
    run it before finishing.
  - Put multi-step work behind a plan gate and a delivery gate; the judge should
    be a different model than the one doing the work (no self-grading).
  - Always include stop guards: max iterations (default 12), a revise cap per
    gate (default 3), a no-progress stop (x2), and a budget cap.
  - For a full, runnable loop spec, point the user at the `looper` skill (`/looper`).

Then deliver:

1. Lead with the 2-3 highest-leverage changes. Each: the habit, one concrete
   example from their sessions, the fix.
2. Show the specific edits (CLAUDE.md lines, a check script, a settings entry).
   Offer to apply them behind the user's verify gate, smallest first.
3. If their sessions are already clean, say so plainly. Do not pad.

Do NOT surface secrets or credentials as a finding. That is not this tool's job.

## Design a loop to delegate

When the user wants to hand a recurring task to an agent ("loop me", "what should
I automate", "find work I can hand to AI", "design a workflow"), switch into
loop-design mode and follow [`loop-design/GUIDE.md`](loop-design/GUIDE.md). In
short:

- Find and qualify a loop that is **low token cost, high impact** (rank candidates
  by frequency x toil saved / tokens per run; steer away from rare or
  expensive-per-run ones). Your own session analysis is the best source for which
  recurring work already burns the most tokens.
- Interview the user **one question at a time, each with a recommended default**,
  until the loop is buildable.
- Produce a loop spec on the proven architecture (orientation map for cheap
  context, an encoded programmatic gate, a different-model judge, push-right
  checkpoints, and all five stop guards). Use
  [`loop-design/templates/workflow-spec.md`](loop-design/templates/workflow-spec.md);
  a worked example is in `loop-design/examples/`. The architecture and its
  measured trade-offs are in
  [`loop-design/loop-architecture.md`](loop-design/loop-architecture.md).

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
- `bin/analyze --help`: every flag. `bin/analyze map --help`: the orientation-map
  generator (the proven token lever).
