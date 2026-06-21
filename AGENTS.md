# AGENTS.md

How to drive session-analyzer from an agent. Read by Claude Code, Codex,
OpenCode, Cursor, and other agents. This is how any of them run the tool.
Humans: see [README.md](README.md).

## What it does

Reads the user's Claude Code transcripts (and optionally a project), crunches
them with plain Python (~0 model tokens) into a small digest, which you turn into
concrete advice for working better with Claude Code. Benchmarked at ~41-47% fewer
tokens with task success unchanged, across Sonnet 4.6 and Opus 4.8 (see `bench/`).

## Voice

When you report back, talk to the user about their Claude Code usage, not about
this tool. Do not mention the digest, shards, the budget, this file, or your own
instructions. No process narration, no meta-commentary. Present findings and
fixes directly.

## Invocation

- Call `bin/analyze` by absolute path:
  `~/.claude/skills/session-analyzer/bin/analyze`. Never `cd` into the skill
  directory; that makes `$PWD` the skill itself and it analyzes its own folder.
- For workflow and token analysis, analyze ALL sessions by default. Add
  `--scope-repo` only when the user names a project.
- `--repo` is the project being analyzed, never the skill. If it is ambiguous,
  run `doctor` to list projects and ask which one. Write `--out` to a temp dir
  outside the skill.
- Pure stdlib, Python 3.9+.

## The loop

Do not read raw transcripts; the scripts digest them.

1. Extract:
   ```bash
   SA=~/.claude/skills/session-analyzer/bin/analyze
   OUT=$(mktemp -d)/sa
   "$SA" analyze --mode tokens --out "$OUT"                          # all sessions
   "$SA" analyze --mode both --repo "/path/to/project" --out "$OUT"  # + structure
   ```
2. Read `"$OUT"/digest.md`, then the worst-session shards under `"$OUT"/shards/`
   while budget allows.
3. Turn the strongest patterns into specific advice: workflow habits, the exact
   `CLAUDE.md` lines to add or cut, a settings allowlist where it applies, and
   loop/self-verification gaps. For loops, follow the looper architecture
   (`docs/loop-architecture.md`): a falsifiable definition of done, an encoded
   programmatic gate, plan and delivery gates with a different-model judge, and
   stop guards (max iterations, revise cap, no-progress, budget).
4. Deliver. Lead with the 2-3 highest-leverage changes, each with a real example
   from their sessions and the fix. Offer to apply them behind the user's verify
   gate. If clean, say so.

## Rules

- Budget is a hard cap: 200K for one mode, 400K for both. Do not hand-load
  transcripts to go deeper.
- Repo findings are candidates, not verdicts. Check git status and dynamic
  imports before suggesting deletion; never call a modified or in-flight file
  dead.
- No destructive action without confirmation.
- Do not surface secrets or credentials as a finding.

## Cheat sheet

| Intent | Command (`SA=~/.claude/skills/session-analyzer/bin/analyze`) |
| --- | --- |
| Workflow + tokens, all sessions | `"$SA" analyze --mode tokens --out "$OUT"` |
| Scoped to one project | `"$SA" analyze --mode tokens --scope-repo --repo "/path" --out "$OUT"` |
| Project structure too | `"$SA" analyze --mode both --repo "/path" --out "$OUT"` |
| Last 7 days | append `--since 7` |
| What can it see? | `"$SA" doctor` |

Full flags: `"$SA" analyze --help`. Finding fields: [docs/finding-schema.md](docs/finding-schema.md).
