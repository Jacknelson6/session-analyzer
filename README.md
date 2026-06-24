<div align="center">

<img src="assets/logo.png" alt="Session Analyzer" width="420">

# Session Analyzer

Reads your Claude Code history and tells you how to fix your sessions so they cost
less and your loops run better. ~41-47% fewer tokens, no quality loss (measured on
Sonnet 4.6 and Opus 4.8).

Works with Claude Code, Codex, OpenCode, and any agent that reads [`AGENTS.md`](AGENTS.md).

</div>

---

## How to use it

`/session-analyzer` — reads your sessions and gives you specific fixes to cut
token waste and tighten the loops where Claude hands work back to you.

| You run | It does |
| --- | --- |
| `/session-analyzer` | Finds token waste and loop gaps across your sessions, with the fixes |
| `/session-analyzer <project>` | Also scans that repo's structure: junk, duplicates, orphans, god-files |
| `/session-analyzer map` | Generates an orientation map for a repo — the single biggest token saver |
| `/session-analyzer loop me` | Turns a recurring task into a cheap, runnable agent loop |

It reports how many tokens you would save, then the ranked fixes. You approve the
changes.

## Install

No dependencies, Python 3.9+. Clone this repo and drop the folder at
`~/.claude/skills/session-analyzer/`. Then use it as above.

## How does it work?
<img width="1672" height="941" alt="image" src="https://github.com/user-attachments/assets/095f3220-ffa0-473c-91f2-f61781d27434" />

See **[docs/how-it-works.md](docs/how-it-works.md)** — the pipeline, a sample
report, and the benchmark proof. Driving the underlying CLI directly:
[AGENTS.md](AGENTS.md) and [docs/usage.md](docs/usage.md).

## License

MIT. See [LICENSE](LICENSE).
