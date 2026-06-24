<div align="center">

<img src="assets/logo.png" alt="Session Analyzer" width="420">

# Session Analyzer

It reads your Claude Code history and tells you how to fix your sessions so they
cost less and your loops run better.

**~41-47% fewer tokens with no quality loss.** It generates the proven token
lever — an orientation map of your repo — on demand with `bin/analyze map`, and
flags the loop gaps that make Claude hand work back to you. Measured on Sonnet
4.6 and Opus 4.8.

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

## The orientation map, on demand

The benchmark below proves the orientation map is the single highest-leverage
token lever (a Pareto win: fewer tokens *and* better output). `bin/analyze map`
generates one for any repo deterministically, in the exact format SA-Bench
validated, so you stop paying the agent to re-derive your repo's layout every
session:

```bash
bin/analyze map --repo "$PWD" --out CLAUDE.md
```

It emits an authoritative file/symbol index plus a read-once rule and the right
verify command for your stack (Python/JS/TS/Go/Rust). Zero model tokens to build.

## Cheat sheet — what you can invoke

This repo ships **two skills** plus the `analyze` CLI. Say a skill's name in
chat, or type its slash command.

### Skills

```
/session-analyzer                  analyze all my sessions for token waste + loop gaps
/session-analyzer both             tokens AND repo structure, ranked together
/session-analyzer repo             just scan this repo for structure problems
/session-analyzer last 7 days      only sessions from the past week
/session-analyzer map              generate the orientation map for this repo

/loop-me                           interview me to find a recurring task worth delegating to AI
/loop-me weekly investor update    grill me into a buildable spec for that specific workflow
```

`/session-analyzer` also fires on plain asks like *"why is Claude burning so many
tokens?"* or *"make my repo cheaper for agents."* `/loop-me` is invoke-only (it
won't trigger itself) — say it explicitly.

### CLI (`bin/analyze`)

```
bin/analyze analyze --mode tokens          # token waste across all sessions
bin/analyze analyze --mode repo --repo .   # repo hygiene scan
bin/analyze analyze --mode both --repo .   # both, ranked together
bin/analyze map --repo . --out CLAUDE.md   # generate the orientation map (proven token lever)
bin/analyze doctor                         # what sessions/projects can it see?
bin/analyze render .sa/run/bundle.json     # re-render a saved run
```

Add `--since 7` for recency, `--format markdown|json` for output, `--fail-under B`
for a CI gate. Every flag: [docs/usage.md](docs/usage.md) or `bin/analyze <command> --help`.

## Proven on SA-Bench

**SA-Bench** is the from-scratch A/B benchmark we built to measure whether a
Claude Code workflow change actually pays: the same tasks run with vs without the
change, real token usage, blind hidden-test grading, on both Sonnet 4.6 and Opus
4.8.

### The orientation map: fewer tokens *and* better output

3-arm run on a 23-file repo with multi-step feature tasks (pass rate / mean tokens):

| config | Sonnet 4.6 | Opus 4.8 |
| --- | --- | --- |
| no map | 67% / 515K | 89% / 1.08M |
| **+ orientation map** | **78% / 524K** | **100% / 889K** |
| + verify gate | 78% / 649K | 100% / 1.27M |

The map is a clean Pareto win: **Opus −17% tokens and 89 → 100% pass; Sonnet
better output at flat cost.** The verify gate matches the map's accuracy but costs
**18-26% more tokens for no gain** — so it is surgical, not a default.

### Token savings across a task suite

Orientation vs none, 8 tasks, task success held at **100% in every arm**:

| model | tokens saved |
| --- | --- |
| Sonnet 4.6 | **~41%** |
| Opus 4.8 | **~47%** |

Full method, the difficulty-ladder cap analysis, and the looper loop architecture:
[bench/README.md](bench/README.md), [docs/loop-cap.md](docs/loop-cap.md),
[docs/loop-architecture.md](docs/loop-architecture.md).

## Install

No dependencies. Python 3.9+.

```bash
git clone https://github.com/Jacknelson6/session-analyzer.git
cd session-analyzer
./bin/analyze --help
```

Use it as a skill: drop the folder at `~/.claude/skills/session-analyzer/`, then
just say **"session analyzer."** The repo also ships a second skill, **`loop-me`**
(`loop-me/SKILL.md`) — copy `loop-me/` to `~/.claude/skills/loop-me/` and invoke
it with **`/loop-me`** to get interviewed into a buildable workflow spec. Full
usage and flags: [docs/usage.md](docs/usage.md). Driving it from an agent:
[AGENTS.md](AGENTS.md).

## License

MIT. See [LICENSE](LICENSE).
