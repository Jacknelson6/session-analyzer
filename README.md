<div align="center">

<img src="assets/logo.png" alt="Session Analyzer" width="420">

# Session Analyzer

It reads your Claude Code history and tells you how to fix your sessions so they
cost less and your loops run better.

**~41-47% fewer tokens, no quality loss, plus encoded verification that takes
first-pass correctness to 100%.** Measured on Sonnet 4.6 and Opus 4.8.

Works with Claude Code, Codex, OpenCode, and any agent that reads [`AGENTS.md`](AGENTS.md).

</div>

---

## How it works

![How Session Analyzer works](assets/how-it-works.png)

```
your sessions  ->  deterministic crunch  ->  small digest  ->  agent advice
(+ optional repo)  plain Python, ~0 tokens   a few KB         copy-paste fixes
```

1. **Extract:** scripts parse your sessions (and optionally a repo). No model tokens.
2. **Read the digest:** a few KB, never the raw transcripts.
3. **Advise:** the agent turns the patterns into copy-pasteable fixes, like
   `CLAUDE.md` rules, an encoded verify gate, and a settings allowlist.

The heavy lifting is deterministic, so it is cheap; the agent only writes the
judgment calls.

## Two modes

- **Sessions** (`--mode tokens`): where you waste tokens *and* where loops break
  (no encoded check, retry loops, hand-backs to you), with the fixes. Cheaper
  runs, better loops.
- **Repo** (`--mode repo`): structure that taxes every agent, like junk,
  duplicates, orphans, and god-files.

`--mode both` runs them together. Details in [docs/usage.md](docs/usage.md).

## Proven

Measured A/B (the same tasks with vs without the tool's recommendations) on
**Sonnet 4.6 and Opus 4.8**, with task success held at **100% in every arm**:

- **Tokens:** ~41% (Sonnet) to ~47% (Opus) fewer.
- **Loops:** an encoded verify gate takes first-pass correctness from 50-67% to
  **100%** on edge-case tasks.

The loops it builds follow the [looper](https://github.com/ksimback/looper)
architecture (plan and delivery gates, a different-model judge, stop guards):
see [docs/loop-architecture.md](docs/loop-architecture.md). Full benchmark tables
and method: [bench/README.md](bench/README.md).

## Install

No dependencies. Python 3.9+.

```bash
git clone https://github.com/Jacknelson6/session-analyzer.git
cd session-analyzer
./bin/analyze --help
```

Use it as a skill: drop the folder at `~/.claude/skills/session-analyzer/`, then
just say **"session analyzer."** Full usage and flags: [docs/usage.md](docs/usage.md).
Driving it from an agent: [AGENTS.md](AGENTS.md).

## License

MIT. See [LICENSE](LICENSE).
