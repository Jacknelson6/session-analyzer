# Token efficiency

_8 sessions · 2M tokens of context processed_

**Grade C**: 69% cache hit-rate across 8 sessions, ~$1.21 reclaimable.

| Metric | Value |
| --- | --- |
| Sessions analyzed | 8 |
| Estimated total cost | $2.68 |
| Cache hit-rate | 69% |
| Reclaimable (cache) | $1.21 |
| Input / output tokens | 550K / 40K |

**Cost per session (oldest to newest):** `█▁▁▁▁▁▂█` latest $0.82

### Highest-waste sessions

| Item | | Value |
| --- | :-- | ---: |
| fixture-07-cache_waster | `████████████` | 33 waste · $0.82 |
| fixture-00-cache_waster | `████████████` | 33 waste · $0.82 |
| fixture-02-big_output | `███████████·` | 30 waste · $0.11 |
| fixture-03-retry_loop | `█████████···` | 24 waste · $0.14 |
| fixture-01-reread_churn | `███████·····` | 20 waste · $0.30 |
| fixture-04-compaction | `██··········` | 6 waste · $0.16 |
| fixture-06-healthy | `············` | 0 waste · $0.17 |
| fixture-05-healthy | `············` | 0 waste · $0.17 |

## Findings (6)

### 1. [MEDIUM] Unbounded tool outputs flood the context window
- **Impact:** ~$0.18 reclaimable
- **Evidence:** 4 tool results exceeded 60,000 chars (~15,000 tokens each).
- **Fix:** Cap noisy commands (head/tail, --max-count, ripgrep over cat, globbed paths). Prefer targeted reads with offset/limit. Pipe long logs to a file and grep it instead of dumping to context.

### 2. [MEDIUM] Files re-read repeatedly within a session
- **Impact:** ~$0.03 reclaimable
- **Evidence:** 1 session re-read the same file >= 3x. Examples: client.ts x10
- **Fix:** Read a file once and keep it in working context; widen the first read instead of paging back. Add a note to the agent instructions: 'do not re-Read a file you already loaded this session.'

### 3. [MEDIUM] Frequent compaction signals context bloat
- **Evidence:** 1 session compacted >= 2x, losing working memory mid-task.
- **Fix:** Trim always-loaded instructions and docs; move rarely-needed reference behind on-demand loads. Smaller standing context means fewer compactions and less re-establishing of state.

### 4. [LOW] Cache misses concentrated in a few sessions
- **Impact:** ~$1.21 reclaimable
- **Evidence:** Overall cache-hit ratio is healthy at 69% (target >= 55%). Only 2 of 8 sessions cache poorly (~$1.21 reclaimable). Worst: fixture- (2%), fixture- (2%).
- **Fix:** Low priority; the overall picture is fine. These outliers are usually short sessions where the cache never warms (a one-off command, an immediate exit). If any are real, recurring tasks, give them a stable prefix; otherwise leave them.

### 5. [LOW] Identical commands re-run (retry loops)
- **Evidence:** 2 sessions repeated an identical Bash command >= 2x, a signal of trial-and-error.
- **Fix:** Encode the working invocation as a documented command or script so the agent does not rediscover it each run. Add failing-fast guards.

### 6. [LOW] High tool-error / permission-denial rate
- **Evidence:** 1 session had a tool-error ratio above 4%.
- **Fix:** Pre-approve the safe, frequently-used commands in settings to cut round-trips; fix the recurring failing invocations at the source.

---

Deterministic pass. Run with an agent synthesis step for tailored CLAUDE.md / settings edits.
