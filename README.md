<div align="center">

<img src="assets/logo.png" alt="Session Analyzer" width="420">

# Session Analyzer

It reads your Claude Code history and tells you how to fix your sessions so they
cost less and your loops run better.

**~41-47% fewer tokens with no quality loss.** It generates the proven token
lever — an orientation map of your repo — on demand, and flags the loop gaps that
make Claude hand work back to you. Measured on Sonnet 4.6 and Opus 4.8.

It also projects, from your own measured usage, **how many tokens you'd save** by
adopting the map — counted only on the sessions where Claude actually re-explored
the tree, so the estimate is grounded, not hype.

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

## What you get

It leads with a grounded estimate of what you'd save, then the ranked fixes:

```
 C   69% cache hit-rate across 8 sessions, ~$1.21 reclaimable.

 → Projected savings
    Adopt the orientation map: ~139K-160K tokens (~8-9% of all tokens).
    basis: 1 of 8 sessions re-explored the tree; benchmark rate 41-47%
    applied only to those.
    Fix cache misses: ~$1.21 more recoverable (see findings).
```

The savings number is your own measured usage times the benchmark rate, counted
only on sessions that actually re-explored the tree — so it is an estimate you
can trust, not a headline figure.

## What it finds

- **Sessions:** where you waste tokens *and* where loops break down — no encoded
  check, retry loops, work handed back to you — with the fixes. Cheaper runs,
  better loops.
- **Repo:** structure that taxes every agent working in it — junk, duplicates,
  orphans, and god-files.

It can run either on its own or both together as one ranked list. Details in
[docs/usage.md](docs/usage.md).

## The orientation map, on demand

The benchmark below proves the orientation map is the single highest-leverage
token lever — a Pareto win: fewer tokens *and* better output. The tool generates
one for any repo deterministically, in the exact format SA-Bench validated: an
authoritative file/symbol index plus a read-once rule and the right verify command
for your stack (Python/JS/TS/Go/Rust). You stop paying the agent to re-derive your
repo's layout every session, and it costs zero model tokens to build.

## What you can invoke

This repo ships **two skills**. Say a skill's name in chat, or type its slash
command — you do not manage paths or flags, that is the agent's job.

| Invoke | What you get |
| --- | --- |
| `/session-analyzer` | Analyze all my sessions for token waste + loop gaps |
| `/session-analyzer both` | Tokens AND repo structure, ranked together |
| `/session-analyzer repo` | Just scan this repo for structure problems |
| `/session-analyzer last 7 days` | Only sessions from the past week |
| `/session-analyzer map` | Generate the orientation map for this repo |
| `/loop-me` | Interview me to find a low-cost, high-impact routine to delegate |
| `/loop-me triage new issues` | Grill me into a buildable, cheap-to-run loop spec for that workflow |

`/session-analyzer` also fires on plain asks like *"why is Claude burning so many
tokens?"* or *"make my repo cheaper for agents."* `/loop-me` is invoke-only — say
it explicitly.

Driving the `analyze` CLI directly — every command, flag, and the exact map
invocation — is in [AGENTS.md](AGENTS.md).

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

No dependencies. Python 3.9+. Clone it, then drop the folder at
`~/.claude/skills/session-analyzer/` and just say **"session analyzer."**

The repo also ships a second skill, **`loop-me`** (`loop-me/SKILL.md`) — copy
`loop-me/` to `~/.claude/skills/loop-me/` and invoke it with **`/loop-me`** to get
interviewed into a buildable, cheap-to-run workflow spec.

Full usage and flags: [docs/usage.md](docs/usage.md). Driving it from an agent:
[AGENTS.md](AGENTS.md).

## License

MIT. See [LICENSE](LICENSE).
