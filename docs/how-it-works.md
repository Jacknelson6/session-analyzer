# How it works

The detail behind the [README](../README.md): the pipeline, what a report looks
like, and the proof. None of this is needed to use the tool — it is here if you
want to know what is happening under the hood.

## The pipeline

![How Session Analyzer works](../assets/how-it-works.png)

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

## What it finds

- **Sessions:** where you waste tokens *and* where loops break down — no encoded
  check, retry loops, work handed back to you — with the fixes. Cheaper runs,
  better loops.
- **Repo:** structure that taxes every agent working in it — junk, duplicates,
  orphans, and god-files.

It can run on either, or both together as one ranked list. Full flag reference:
[usage.md](usage.md).

## What a report looks like

It leads with a grounded estimate of what you would save, then the ranked fixes:

```
 C   69% cache hit-rate across 8 sessions, ~$1.21 reclaimable.

 → Projected savings
    Adopt the orientation map: ~139K-160K tokens (~8-9% of all tokens).
    basis: 1 of 8 sessions re-explored the tree; benchmark rate 41-47%
    applied only to those.
    Fix cache misses: ~$1.21 more recoverable (see findings).
```

The savings number is your own measured usage times the benchmark rate, counted
only on sessions that actually re-explored the tree — so it is grounded, not a
headline figure.

## The orientation map

The benchmark below shows the orientation map is the single highest-leverage token
lever — a Pareto win: fewer tokens *and* better output. The tool generates one for
any repo deterministically: an authoritative file/symbol index plus a read-once
rule and the right verify command for your stack (Python/JS/TS/Go/Rust). The agent
stops re-deriving your repo's layout every session, and it costs zero model tokens
to build.

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

Full method, the difficulty-ladder cap analysis, and the loop architecture:
[../bench/README.md](../bench/README.md), [loop-cap.md](loop-cap.md),
[loop-architecture.md](loop-architecture.md).
