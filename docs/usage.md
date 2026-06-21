# Usage & reference

The detail behind the [README](../README.md). To drive the tool from an agent,
see [AGENTS.md](../AGENTS.md).

## Talking to it (as a skill)

You don't type commands. Say "session analyzer" (or `/session-analyzer`), then
what you want. The agent picks the mode, points it at your project, and runs it.

| Say this | What you get |
| --- | --- |
| "session analyzer, tokens" | Token waste across all sessions |
| "session analyzer, tokens, just this repo" | Token waste, scoped to the current project |
| "session analyzer, clean up this repo" | Repo hygiene scan |
| "session analyzer, both" | Tokens and repo, ranked together |
| "session analyzer, both, last 7 days, as markdown" | Both, recent sessions, PR-ready output |
| "why is Claude burning so many tokens?" | Token waste (no trigger phrase needed) |
| "what sessions can it see?" | Discovery check |

You do not manage paths or flags. That is the agent's job.

## By hand (CLI)

```bash
# all sessions
bin/analyze analyze --mode tokens

# scoped to the current repo
bin/analyze analyze --mode tokens --scope-repo --repo "$PWD"

# repo hygiene
bin/analyze analyze --mode repo --repo "$PWD"

# both, write artifacts, render Markdown
bin/analyze analyze --mode both --repo "$PWD" --scope-repo --out .sa/run --format markdown

# re-render a saved run (auto-merges a sibling synthesis.json)
bin/analyze render .sa/run/bundle.json --format markdown

# what can it see?
bin/analyze doctor

# CI gate: fail under grade B
bin/analyze analyze --mode repo --repo "$PWD" --fail-under B

# last 7 days only
bin/analyze analyze --mode tokens --since 7
```

Flags: `--top N`, `--max-sessions N`, `--since DAYS`, `--projects-root PATH`,
`--format terminal|markdown|json`, `--color auto|always|never`,
`--fail-under A..F`, and the four `--price-*` overrides for exact cost.

## What each mode finds

### Sessions (`--mode tokens`)

Where your sessions waste tokens, and where loops break down:

- Cache misses — a low cache-hit ratio means paying full input rate for context
  that could be cached. Usually the biggest lever.
- The same file read 3+ times in one session.
- Oversized tool outputs flooding the context window.
- Retry loops — identical commands re-run, usually a missing encoded check.
- Loop / self-verification gaps — changes that shipped without running
  tests/build, and stretches where you had to step in turn after turn.
- Context thrash — frequent compaction from a bloated standing prompt.

The fixes: `CLAUDE.md` rules, an encoded verify gate (the check Claude can't
infer), falsifiable success criteria, a settings allowlist.

### Repo (`--mode repo`)

Structure that taxes every agent working in the repo:

- Junk artifacts: committed logs, `.DS_Store`, `.orig`/`.bak`/`.tmp`.
- Exact and near-duplicate files (near-dup catches reformatted copy-paste).
- Orphan library modules nothing imports.
- Oversized files.
- Commented-out code blocks (JSDoc excluded).
- Ambiguous basenames: the same filename across many directories.

Generated, minified, and vendored files are counted for size but excluded from
refactor findings, so it does not flag what is not yours to change. See
[../OPTIMIZATION_LOG.md](../OPTIMIZATION_LOG.md).

`--mode both` runs the two together and ranks across them.

## Works with other agents

The tool is driven by [AGENTS.md](../AGENTS.md), which Claude Code, Codex,
OpenCode, Cursor, and other agents read — so any of them can run it. `bin/analyze`
is plain stdlib Python and runs anywhere. The repo scan and the recommendations
(orientation map, verify gate) are tool-agnostic. Session-token analysis currently
parses Claude Code transcripts (`~/.claude/projects`); point `--projects-root`
elsewhere for other tools (broader transcript-format support is on the roadmap).

## Architecture

```
bin/analyze            CLI shim
src/
  sessions.py          transcript discovery + parsing
  extract.py           token-waste metrics + findings
  repo_scan.py         repo hygiene scan
  config.py            ignore/classify rules
  pricing.py           token -> USD
  budget.py            the token ledger
  findings.py          the Finding contract
  digest.py            budget-bounded agent artifacts
  report.py            report -> render bundle
  render.py            terminal + markdown output
  theme.py             palette, glyphs, bars (NO_COLOR aware)
tests/                 unittest suite + fixtures
bench/                 the A/B benchmark (proof of the savings)
docs/                  schemas + this guide
```

## Limits

- Token counts are exact (from `usage`). Reclaimable-cost figures are estimates
  that depend on your prices and on caching being achievable.
- Orphan detection is a heuristic that traces JS/TS-style imports, so it
  over-flags files in Python and other languages. Confirm with `knip`/`ts-prune`.
- It reads transcripts and source read-only. It never changes your repo or its
  history; it only writes under `.sa/` in a run you ask for.
